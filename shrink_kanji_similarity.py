#!/usr/bin/env python3
"""
Shrink Niai kanji similarity data to only:
  - Character
  - Frequency
  - Similar (list of {Kanji, Score})

Also prints a small EDA:
  - total entries
  - entries with similar > 0
  - avg / max similar count
  - top 10 kanji by similar count (with the count)

Source lookup (first existing is used):
  1) niai data/data/kanjis.json           (path with space)
  2) niai/backend/src/Niai/data/kanjis.json

Outputs:
  - kanjis_min.json       (reduced data)
  - kanjis_min_stats.txt  (text stats)
"""

import json
from pathlib import Path

DEFAULT_SOURCES = [
    Path("niai data/data/kanjis.json"),
    Path("niai/backend/src/Niai/data/kanjis.json"),
]
OUT_JSON = Path("kanjis_min.json")
OUT_STATS = Path("kanjis_min_stats.txt")


def pick_source():
    for p in DEFAULT_SOURCES:
        if p.exists():
            return p
    raise FileNotFoundError("kanjis.json not found in expected locations.")


def load_kanjis(src: Path):
    print(f"Loading {src} ...")
    data = json.loads(src.read_text(encoding="utf-8"))
    print(f"Loaded {len(data)} entries.")
    return data


def reduce_fields(data):
    reduced = []
    for entry in data:
        reduced.append(
            {
                "Character": entry.get("Character"),
                "Frequency": entry.get("Frequency"),
                "Similar": entry.get("Similar", []),
            }
        )
    return reduced


def compute_stats(reduced):
    total = len(reduced)
    sim_counts = [len(x.get("Similar", [])) for x in reduced]
    with_sim = sum(1 for c in sim_counts if c > 0)
    avg = sum(sim_counts) / total if total else 0
    max_sim = max(sim_counts) if sim_counts else 0
    # top 10 by similar count
    top = sorted(
        ((r["Character"], len(r.get("Similar", []))) for r in reduced),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    return {
        "total": total,
        "with_similar": with_sim,
        "avg_similar_count": avg,
        "max_similar_count": max_sim,
        "top10_by_count": top,
    }


def save_outputs(reduced, stats):
    OUT_JSON.write_text(json.dumps(reduced, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = []
    lines.append("=== Kanji Similarity EDA ===")
    lines.append(f"Total entries: {stats['total']}")
    lines.append(f"Entries with similar > 0: {stats['with_similar']}")
    lines.append(f"Avg similar count: {stats['avg_similar_count']:.2f}")
    lines.append(f"Max similar count: {stats['max_similar_count']}")
    lines.append("Top 10 by similar count:")
    for ch, cnt in stats["top10_by_count"]:
        lines.append(f"  {ch}: {cnt}")
    text = "\n".join(lines)
    OUT_STATS.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nSaved reduced data -> {OUT_JSON}")
    print(f"Saved stats -> {OUT_STATS}")


def main():
    src = pick_source()
    data = load_kanjis(src)
    reduced = reduce_fields(data)
    stats = compute_stats(reduced)
    save_outputs(reduced, stats)


if __name__ == "__main__":
    main()


