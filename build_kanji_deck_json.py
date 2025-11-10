#!/usr/bin/env python3
"""
Build a JSON payload for a kanji-only deck.

For each kanji (from unique_kanji_chars_all.json), produce:
  - kanji (front)
  - meaning (first meaning string)
  - kunyomi
  - onyomi
  - vocab_samples: up to 4 words containing the kanji (prefer n3.csv, fallback n2.csv)
  - similar: up to 4 similar kanji with score and meaning

Sources:
  - unique_kanji_chars_all.json   (list of kanji to include)
  - n3.csv (first column words), n2.csv as fallback
  - kanjis_min.json (similar list)
  - niai data/data/kanjis.json (full kanji info: meanings, readings)

Output:
  - kanji_deck_data.json
"""

import csv
import json
from pathlib import Path
from typing import Dict, List

# Resolve paths relative to this script's directory
ROOT = Path(__file__).resolve().parent

# Candidate locations (first existing is used)
KANJI_LIST_CANDIDATES = [
    ROOT / "unique_kanji_chars_all.json",
    ROOT / "niai data/data/unique_kanji_chars_all.json",
    ROOT / "niai/data/data/unique_kanji_chars_all.json",
]
KANJIS_FULL_CANDIDATES = [
    ROOT / "niai data/data/kanjis.json",
    ROOT / "niai/data/data/kanjis.json",
    ROOT / "kanjis.json",
]

KANJI_LIST_PATH: Path  # resolved below
KANJIS_FULL_PATH: Path  # resolved below

VOCAB_N3 = ROOT / "n3.csv"
VOCAB_N2 = ROOT / "n2.csv"
KANJIS_MIN_CANDIDATES = [
    ROOT / "kanjis_min.json",
    ROOT / "niai data/data/kanjis_min.json",
    ROOT / "niai/data/data/kanjis_min.json",
]

OUTPUT_JSON = ROOT / "kanji_deck_data.json"


def resolve_first(paths: List[Path], description: str) -> Path:
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"Missing {description}. Checked: " + ", ".join(str(p) for p in paths))


def load_kanji_list() -> List[str]:
    global KANJI_LIST_PATH
    KANJI_LIST_PATH = resolve_first(KANJI_LIST_CANDIDATES, "kanji list")
    return json.loads(KANJI_LIST_PATH.read_text(encoding="utf-8"))


def load_kanji_info() -> Dict[str, dict]:
    global KANJIS_FULL_PATH
    KANJIS_FULL_PATH = resolve_first(KANJIS_FULL_CANDIDATES, "kanjis.json")
    data = json.loads(KANJIS_FULL_PATH.read_text(encoding="utf-8"))
    return {k["Character"]: k for k in data if k.get("Character")}


def load_similarity() -> Dict[str, List[dict]]:
    sim_path = resolve_first(KANJIS_MIN_CANDIDATES, "similarity data (kanjis_min.json)")
    data = json.loads(sim_path.read_text(encoding="utf-8"))
    return {e["Character"]: e.get("Similar", []) for e in data if e.get("Character")}


def load_vocab_words(path: Path) -> List[str]:
    if not path.exists():
        return []
    words = []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                continue  # skip header
            if not row:
                continue
            w = row[0].strip()
            if w:
                words.append(w)
    return words


def build_vocab_index() -> Dict[str, List[str]]:
    vocab_n3 = load_vocab_words(VOCAB_N3)
    vocab_n2 = load_vocab_words(VOCAB_N2)
    def index(words: List[str]) -> Dict[str, List[str]]:
        m: Dict[str, List[str]] = {}
        for w in words:
            for ch in set(w):  # unique chars per word
                m.setdefault(ch, []).append(w)
        return m
    idx3 = index(vocab_n3)
    idx2 = index(vocab_n2)
    return idx3, idx2


def main():
    kanji_list = load_kanji_list()
    kanji_info = load_kanji_info()
    sim_map = load_similarity()
    idx3, idx2 = build_vocab_index()

    output = []
    for k in kanji_list:
        info = kanji_info.get(k, {})
        meanings = info.get("Meanings") or []
        meaning = meanings[0] if meanings else ""
        kunyomi = info.get("Kunyomi") or ""
        onyomi = info.get("Onyomi") or ""

        # vocab samples: prefer N3, fallback N2
        samples = idx3.get(k, [])[:4]
        if len(samples) < 4:
            more = [w for w in idx2.get(k, []) if w not in samples]
            samples.extend(more[: 4 - len(samples)])

        # similars: up to 4, include meaning
        similars_raw = sim_map.get(k, [])[:4]
        similars = []
        for s in similars_raw:
            sk = s.get("Kanji")
            sscore = s.get("Score", 0)
            smeaning_list = kanji_info.get(sk, {}).get("Meanings") or []
            smeaning = smeaning_list[0] if smeaning_list else ""
            similars.append({"kanji": sk, "score": sscore, "meaning": smeaning})

        output.append(
            {
                "kanji": k,
                "meaning": meaning,
                "kunyomi": kunyomi,
                "onyomi": onyomi,
                "vocab_samples": samples,
                "similar": similars,
            }
        )

    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Wrote {len(output)} entries to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()

