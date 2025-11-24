#!/usr/bin/env python3
"""
EDA + fix for kanji_deck_data.json:
- Report missing counts per field.
- Fill missing meaning/kunyomi/onyomi/samples/similar using available sources:
  * kanjis.json (full)
  * kanjidic2.xml (fallback)
  * vocab samples from n3.csv, then n2.csv
  * similar from kanjis_min.json with meanings from kanjis.json/kanjidic2

Outputs:
- kanji_deck_data_filled.json (filled version)
- EDA printed to stdout
"""

import csv
import json
import xml.etree.ElementTree as ET
import gzip
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent

# Cache for jisho lookups (in-memory during run)
JISHO_CACHE: Dict[str, dict] = {}

"""
Set ONLINE_FALLBACK = True to attempt filling missing meaning/onyomi/kunyomi
from an online source (jisho.org). This is best-effort and will be skipped
if network is unavailable.
"""
ONLINE_FALLBACK = False

# Inputs
DECK_JSON = ROOT / "kanji_deck_data.json"
KANJIS_FULL_CANDIDATES = [
    ROOT / "niai data/data/kanjis.json",
    ROOT / "niai/data/data/kanjis.json",
    ROOT / "kanjis.json",
]
KANJIS_MIN_CANDIDATES = [
    ROOT / "kanjis_min.json",
    ROOT / "niai data/data/kanjis_min.json",
    ROOT / "niai/data/data/kanjis_min.json",
]
KANKIDIC_CANDIDATES = [
    ROOT / "kanjidic2.xml",
    ROOT / "niai data/data/kanjidic2.xml",
    ROOT / "niai/data/data/kanjidic2.xml",
    ROOT / "kanjidic2.xml.gz",
    ROOT / "niai data/data/kanjidic2.xml.gz",
    ROOT / "niai/data/data/kanjidic2.xml.gz",
]
VOCAB_N3_CANDIDATES = [
    ROOT / "n3.csv",
    ROOT / "niai data/data/n3.csv",
    ROOT / "niai/data/data/n3.csv",
]
VOCAB_N2_CANDIDATES = [
    ROOT / "n2.csv",
    ROOT / "niai data/data/n2.csv",
    ROOT / "niai/data/data/n2.csv",
]
VOCAB_N4_CANDIDATES = [
    ROOT / "n4.csv",
    ROOT / "niai data/data/n4.csv",
    ROOT / "niai/data/data/n4.csv",
]
VOCAB_N5_CANDIDATES = [
    ROOT / "n5.csv",
    ROOT / "niai data/data/n5.csv",
    ROOT / "niai/data/data/n5.csv",
]

# Output
OUT_JSON = ROOT / "kanji_deck_data_filled.json"


def resolve_first(paths: List[Path], desc: str) -> Path:
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"Missing {desc}. Checked: " + ", ".join(str(p) for p in paths))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_kanji_full() -> Dict[str, dict]:
    src = resolve_first(KANJIS_FULL_CANDIDATES, "kanjis.json")
    data = load_json(src)
    print(f"Loaded kanjis.json from {src} ({len(data)} entries)")
    return {k["Character"]: k for k in data if k.get("Character")}


def load_similarity() -> Dict[str, List[dict]]:
    src = resolve_first(KANJIS_MIN_CANDIDATES, "kanjis_min.json")
    data = load_json(src)
    print(f"Loaded similarity from {src} ({len(data)} entries)")
    sim_map = {e["Character"]: e.get("Similar", []) for e in data if e.get("Character")}
    return sim_map


def build_vocab_index() -> Tuple[Dict[str, List[Tuple[str, str]]], Dict[str, List[Tuple[str, str]]], Dict[str, List[Tuple[str, str]]], Dict[str, List[Tuple[str, str]]]]:
    def load_csv_with_meanings(path: Path) -> List[Tuple[str, str]]:
        """Return list of (expression, meaning)."""
        if not path.exists():
            return []
        rows = []
        with path.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0 or not row:
                    continue
                expr = row[0].strip()
                meaning = row[2].strip() if len(row) > 2 else ""
                if expr:
                    rows.append((expr, meaning))
        return rows

    def index(rows: List[Tuple[str, str]]) -> Dict[str, List[Tuple[str, str]]]:
        m: Dict[str, List[Tuple[str, str]]] = {}
        for expr, meaning in rows:
            for ch in set(expr):
                m.setdefault(ch, []).append((expr, meaning))
        return m

    n3_path = resolve_first(VOCAB_N3_CANDIDATES, "n3.csv")
    n2_path = resolve_first(VOCAB_N2_CANDIDATES, "n2.csv")
    n4_path = resolve_first(VOCAB_N4_CANDIDATES, "n4.csv")
    n5_path = resolve_first(VOCAB_N5_CANDIDATES, "n5.csv")
    n3_rows = load_csv_with_meanings(n3_path)
    n2_rows = load_csv_with_meanings(n2_path)
    n4_rows = load_csv_with_meanings(n4_path)
    n5_rows = load_csv_with_meanings(n5_path)
    print(f"Loaded vocab: N3 rows={len(n3_rows)}, N2 rows={len(n2_rows)}")
    print(f"Loaded vocab: N4 rows={len(n4_rows)}, N5 rows={len(n5_rows)}")
    idx3 = index(n3_rows)
    idx2 = index(n2_rows)
    idx4 = index(n4_rows)
    idx5 = index(n5_rows)
    print(f"Index sizes: N3 chars={len(idx3)}, N2 chars={len(idx2)}, N4 chars={len(idx4)}, N5 chars={len(idx5)}")
    return idx3, idx2, idx4, idx5


# Kanjidic2 parsing
def load_kanjidic2():
    try:
        path = resolve_first(KANKIDIC_CANDIDATES, "kanjidic2.xml")
    except FileNotFoundError:
        print("kanjidic2.xml not found, skipping that fallback.")
        return {}
    print(f"Loaded kanjidic2 from {path}")
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as f:
            tree = ET.parse(f)
    else:
        tree = ET.parse(path)
    root = tree.getroot()
    ns = {"k": "http://www.edrdg.org/kanjidic/kanjidic2"}
    data = {}
    for ch in root.findall("k:character", ns):
        literal = ch.findtext("k:literal", default="", namespaces=ns)
        if not literal:
            continue
        meanings = []
        kunyomi = []
        onyomi = []
        for rm in ch.findall("k:reading_meaning/k:rmgroup", ns):
            for rd in rm.findall("k:reading", ns):
                rt = rd.attrib.get("r_type", "")
                if rt == "ja_on":
                    onyomi.append(rd.text or "")
                elif rt == "ja_kun":
                    kunyomi.append(rd.text or "")
            for m in rm.findall("k:meaning", ns):
                # Only meanings without lang or lang="en"
                if m.attrib.get("m_lang", "en") == "en":
                    meanings.append(m.text or "")
        data[literal] = {
            "meanings": meanings,
            "kunyomi": kunyomi,
            "onyomi": onyomi,
        }
    return data


def take_first(lst):
    if not lst:
        return ""
    return lst[0] if isinstance(lst, list) else lst


def scrape_jisho(kanji: str) -> dict:
    """
    Best-effort scrape from jisho.org for meanings and readings.
    Returns dict with optional meanings (list), kunyomi (str), onyomi (str).
    """
    try:
        url = f"https://jisho.org/search/{kanji}%20%23kanji"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code != 200:
            return {}
        soup = BeautifulSoup(resp.text, "html.parser")

        # Meanings
        meanings = []
        meaning_div = soup.find("div", class_="kanji-details__main-meanings")
        if meaning_div:
            meanings = [m.strip() for m in meaning_div.text.strip().split(",") if m.strip()]

        kunyomi = ""
        onyomi = ""
        readings = soup.find_all("dl", class_="kanji-details__main-readings-list")
        for dl in readings:
            dt = dl.find("dt")
            dd = dl.find("dd")
            if not dt or not dd:
                continue
            label = dt.text.strip().lower()
            val = dd.text.strip().replace("\n", " ").strip()
            if "kun" in label:
                kunyomi = val
            if "on" in label:
                onyomi = val

        return {"meanings": meanings, "kunyomi": kunyomi, "onyomi": onyomi}
    except Exception:
        return {}


def fill_entry(entry, k_full, kd2, sim_map, idx3, idx2, idx4, idx5):
    k = entry["kanji"]

    info = k_full.get(k, {})
    kd = kd2.get(k, {})
    jisho = {}
    if ONLINE_FALLBACK and (not entry.get("meaning") or not entry.get("kunyomi") or not entry.get("onyomi")):
        if k in JISHO_CACHE:
            jisho = JISHO_CACHE[k]
        else:
            jisho = scrape_jisho(k)
            JISHO_CACHE[k] = jisho

    # meaning
    if not entry.get("meaning"):
        entry["meaning"] = (
            take_first(info.get("Meanings"))
            or take_first(kd.get("meanings"))
            or take_first(jisho.get("meanings", []))
        )

    # kunyomi
    if not entry.get("kunyomi"):
        entry["kunyomi"] = (
            info.get("Kunyomi")
            or "; ".join(kd.get("kunyomi", []))
            or jisho.get("kunyomi", "")
        )

    # onyomi
    if not entry.get("onyomi"):
        entry["onyomi"] = (
            info.get("Onyomi")
            or "; ".join(kd.get("onyomi", []))
            or jisho.get("onyomi", "")
        )

    # vocab samples
    if not entry.get("vocab_samples"):
        samples = []
        for source in (idx3, idx2, idx4, idx5):
            if len(samples) >= 4:
                break
            more = []
            for expr, meaning in source.get(k, []):
                formatted = f"{expr} ({meaning})" if meaning else expr
                if formatted not in samples:
                    more.append(formatted)
            samples.extend(more[: max(0, 4 - len(samples))])
        entry["vocab_samples"] = samples

    # similar
    if not entry.get("similar"):
        sims = sim_map.get(k, [])[:4]
        similar_out = []
        for s in sims:
            sk = s.get("Kanji")
            score = s.get("Score", 0)
            s_info = k_full.get(sk, {})
            s_mean = take_first(s_info.get("Meanings")) or take_first(kd2.get(sk, {}).get("meanings")) if kd2 else ""
            similar_out.append({"kanji": sk, "score": score, "meaning": s_mean})
        entry["similar"] = similar_out


def eda(entries):
    fields = ["meaning", "kunyomi", "onyomi", "vocab_samples", "similar"]
    print("=== Missing counts BEFORE fill ===")
    for f in fields:
        missing = sum(1 for e in entries if not e.get(f))
        print(f"{f}: {missing}")
    print()
    # show a few examples
    for f in fields:
        miss = [e["kanji"] for e in entries if not e.get(f)]
        if miss:
            print(f"{f} missing sample: {miss[:10]}")


def eda_after(entries):
    fields = ["meaning", "kunyomi", "onyomi", "vocab_samples", "similar"]
    print("\n=== Missing counts AFTER fill ===")
    for f in fields:
        missing = sum(1 for e in entries if not e.get(f))
        print(f"{f}: {missing}")
    print()
    for f in fields:
        miss = [e["kanji"] for e in entries if not e.get(f)]
        if miss:
            print(f"{f} still missing sample: {miss[:10]}")


def main():
    entries = load_json(DECK_JSON)

    eda(entries)

    k_full = load_kanji_full()
    kd2 = load_kanjidic2()
    sim_map = load_similarity()
    idx3, idx2, idx4, idx5 = build_vocab_index()

    for e in entries:
        fill_entry(e, k_full, kd2, sim_map, idx3, idx2, idx4, idx5)

    eda_after(entries)

    OUT_JSON.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ Wrote filled deck JSON to {OUT_JSON}")


if __name__ == "__main__":
    main()

