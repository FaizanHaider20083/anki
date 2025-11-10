#!/usr/bin/env python3
"""
Build a single source of truth for unique kanji words from N2–N5 CSVs.

Rules:
1) Ignore header row.
2) Use only the first column.
3) Strip leading "~" prefixes.
4) Drop anything inside parentheses/brackets ((), （）, [], 【】).
5) Keep only kanji characters (and iteration mark 々); discard kana/romaji.
6) Skip entries that end up empty or contain no kanji.

Outputs:
- unique_kanji_all.txt      (one kanji term per line, sorted)
- unique_kanji_by_level.json (per-level unique lists)
- Summary printed to stdout (counts, per-level uniques, total uniques)
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Set

# Input files
FILES = {
    "N2": "n2.csv",
    "N3": "n3.csv",
    "N4": "n4.csv",
    "N5": "n5.csv",
}

# Outputs
OUT_ALL = Path("unique_kanji_all.txt")
OUT_JSON = Path("unique_kanji_by_level.json")


# Kanji ranges + iteration mark
KANJI_PATTERN = re.compile(
    r"["
    r"\u4E00-\u9FFF"          # CJK Unified Ideographs
    r"\u3400-\u4DBF"          # CJK Extension A
    r"\U00020000-\U0002A6DF"  # CJK Extension B
    r"\u3005"                 # 々 iteration mark
    r"]+"
)


def clean_entry(raw: str) -> str:
    """Apply all cleaning steps and return kanji-only string, or '' if none."""
    if not raw:
        return ""

    s = raw.strip()

    # Remove leading ~ and whitespace after it
    if s.startswith("~"):
        s = s.lstrip("~").strip()

    # Remove bracketed/parenthetical content ((), （）, [], 【】)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"（[^）]*）", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = re.sub(r"【[^】]*】", "", s)

    # Collapse extra spaces
    s = re.sub(r"\s+", " ", s).strip()

    # Extract only kanji/iteration-mark characters
    kanji_parts = KANJI_PATTERN.findall(s)
    if not kanji_parts:
        return ""

    cleaned = "".join(kanji_parts)
    return cleaned


def load_and_clean(path: Path) -> List[str]:
    words = []
    with path.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                # Skip header
                continue
            if not row:
                continue
            cell = row[0].strip()
            cleaned = clean_entry(cell)
            if cleaned:
                words.append(cleaned)
    return words


def main():
    per_level: Dict[str, Set[str]] = {}
    raw_counts: Dict[str, int] = {}

    for level, fname in FILES.items():
        p = Path(fname)
        if not p.exists():
            print(f"❌ Missing file: {fname}")
            continue
        words = load_and_clean(p)
        raw_counts[level] = len(words)
        per_level[level] = set(words)

    if not per_level:
        print("No files processed.")
        return

    # Combined unique
    all_unique = set().union(*per_level.values())

    # Outputs
    OUT_ALL.write_text("\n".join(sorted(all_unique)), encoding="utf-8")
    OUT_JSON.write_text(
        json.dumps(
            {lvl: sorted(list(vals)) for lvl, vals in per_level.items()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Summary
    print("=== Kanji EDA (cleaned) ===")
    for lvl in sorted(per_level.keys()):
        print(f"{lvl}: raw rows (after header skip) = {raw_counts[lvl]}, unique kanji = {len(per_level[lvl])}")
    print(f"\nTotal unique kanji across N2–N5: {len(all_unique)}")

    # Pairwise overlaps
    levels = sorted(per_level.keys())
    print("\n=== Pairwise overlaps ===")
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            l1, l2 = levels[i], levels[j]
            inter = per_level[l1] & per_level[l2]
            print(f"{l1} ∩ {l2}: {len(inter)}")


if __name__ == "__main__":
    main()


