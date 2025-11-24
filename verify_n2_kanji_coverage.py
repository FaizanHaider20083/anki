#!/usr/bin/env python3
"""
Verify JLPT kanji coverage (N2-N5) against an external list.

External source: davidluzgouveia/kanji-data (GitHub)
Local list: kanji_deck_data_filled.json (the source of truth)

Reports per level:
  - Count in external list
  - Missing in local (present in external)
"""

import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Source of truth - the kanji deck we built
LOCAL_DECK = [
    ROOT / "kanji_deck_data_filled.json",
    ROOT / "kanji_deck_data.json",
]

# Full kanji.json with jlpt field
EXTERNAL_URL = "https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json"

# Levels to check
LEVELS_TO_CHECK = [2, 3, 4, 5]  # N2, N3, N4, N5


def resolve_first(paths, desc):
    for p in paths:
        if p.exists():
            return p
    return None


def load_local():
    """Load kanji from our deck JSON (source of truth)."""
    path = resolve_first(LOCAL_DECK, "kanji_deck_data_filled.json")
    if not path:
        raise FileNotFoundError("kanji_deck_data_filled.json not found.")
    
    data = json.loads(path.read_text(encoding="utf-8"))
    # Extract the "kanji" field from each entry
    kanji_set = set()
    for entry in data:
        k = entry.get("kanji", "")
        if k:
            kanji_set.add(k)
    
    print(f"Loaded {len(kanji_set)} kanji from {path.name}")
    return kanji_set


def load_external():
    """Load kanji from external source, grouped by JLPT level."""
    print(f"Fetching kanji data from GitHub...")
    resp = requests.get(EXTERNAL_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    
    data = resp.json()
    print(f"✓ Fetched {len(data)} total kanji entries")
    
    # Debug: print a sample entry to understand structure
    sample_keys = list(data.keys())[:3] if isinstance(data, dict) else []
    if sample_keys:
        print(f"  Sample entries for debugging:")
        for k in sample_keys:
            print(f"    '{k}': {data[k]}")
    
    # Group by JLPT level
    by_level = {level: set() for level in LEVELS_TO_CHECK}
    
    if isinstance(data, dict):
        for kanji_char, info in data.items():
            if isinstance(info, dict):
                # Try different possible field names for JLPT level
                jlpt = info.get("jlpt") or info.get("jlpt_new") or info.get("jlpt_old")
                
                # Handle string values like "N2" or "n2"
                if isinstance(jlpt, str):
                    jlpt_str = jlpt.upper().replace("N", "")
                    try:
                        jlpt = int(jlpt_str)
                    except ValueError:
                        jlpt = None
                
                if jlpt in LEVELS_TO_CHECK:
                    by_level[jlpt].add(kanji_char)
    
    for level in LEVELS_TO_CHECK:
        print(f"  N{level}: {len(by_level[level])} kanji")
    
    return by_level


def main():
    local = load_local()
    external_by_level = load_external()
    
    print("\n" + "=" * 50)
    
    total_missing = 0
    all_missing = set()
    
    for level in LEVELS_TO_CHECK:
        external = external_by_level[level]
        missing = external - local
        
        print(f"\n=== N{level} Kanji Coverage ===")
        print(f"External N{level} kanji count: {len(external)}")
        print(f"Missing (not in your deck): {len(missing)}")
        
        if missing:
            sample = sorted(list(missing))[:20]
            print(f"  Missing kanji: {''.join(sample)}")
            if len(missing) > 20:
                print(f"  ... and {len(missing) - 20} more")
            all_missing.update(missing)
        else:
            print(f"  ✅ All N{level} kanji present!")
        
        total_missing += len(missing)
    
    # Summary
    print("\n" + "=" * 50)
    print("=== SUMMARY ===")
    total_external = sum(len(external_by_level[l]) for l in LEVELS_TO_CHECK)
    print(f"Your deck has: {len(local)} kanji")
    print(f"External JLPT N2-N5 total: {total_external} kanji")
    print(f"Total missing from your deck: {total_missing}")
    
    if total_missing == 0:
        print("\n✅ Your deck covers all N2-N5 kanji!")
    else:
        print(f"\n⚠️  {total_missing} kanji are missing from your deck.")
        if all_missing and len(all_missing) <= 100:
            print(f"\nAll missing kanji:\n{''.join(sorted(all_missing))}")


if __name__ == "__main__":
    main()
