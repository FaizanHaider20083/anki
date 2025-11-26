#!/usr/bin/env python3
"""
1. Add missing kanji 隻 to kanji_deck_data_filled.json
2. EDA: Check coverage of top 1000 most frequent kanji
"""

import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECK_JSON = ROOT / "kanji_deck_data_filled.json"
EXTERNAL_URL = "https://raw.githubusercontent.com/davidluzgouveia/kanji-data/master/kanji.json"

# Missing kanji to add (from Jisho.org)
MISSING_KANJI = {
    "kanji": "隻",
    "meaning": "counter for ships, vessels",
    "kunyomi": "",
    "onyomi": "セキ",
    "vocab_samples": [
        "一隻 (いっせき) - one ship/vessel",
        "隻眼 (せきがん) - one eye",
        "隻手 (せきしゅ) - one hand",
        "数隻 (すうせき) - several ships"
    ],
    "similar": [
        {
            "kanji": "雙",
            "score": 0.8,
            "meaning": "pair, set"
        },
        {
            "kanji": "集",
            "score": 0.6,
            "meaning": "gather, collect"
        },
        {
            "kanji": "售",
            "score": 0.5,
            "meaning": "sell"
        }
    ]
}


def add_missing_kanji():
    """Add the missing kanji to the deck JSON."""
    print("Loading deck JSON...")
    data = json.loads(DECK_JSON.read_text(encoding="utf-8"))
    
    # Check if already exists
    existing = {e["kanji"] for e in data}
    if MISSING_KANJI["kanji"] in existing:
        print(f"  ✓ Kanji {MISSING_KANJI['kanji']} already exists in deck")
        return data
    
    # Add it
    data.append(MISSING_KANJI)
    print(f"  ✓ Added kanji {MISSING_KANJI['kanji']} to deck")
    
    # Save
    DECK_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Saved to {DECK_JSON}")
    
    return data


def frequency_eda(deck_data):
    """Check coverage of top 1000 most frequent kanji."""
    print("\n" + "=" * 50)
    print("Fetching frequency data from GitHub...")
    
    resp = requests.get(EXTERNAL_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    external = resp.json()
    
    # Build list of kanji sorted by frequency
    freq_list = []
    for kanji_char, info in external.items():
        freq = info.get("freq")
        if freq is not None and isinstance(freq, int):
            freq_list.append((kanji_char, freq))
    
    # Sort by frequency (lower = more common)
    freq_list.sort(key=lambda x: x[1])
    
    print(f"✓ Found {len(freq_list)} kanji with frequency data")
    
    # Get top 1000
    top_1000 = set(k for k, f in freq_list[:1000])
    print(f"  Top 1000 most frequent kanji extracted")
    
    # Get our deck kanji
    our_kanji = set(e["kanji"] for e in deck_data)
    print(f"  Our deck has {len(our_kanji)} kanji")
    
    # Calculate coverage
    covered = top_1000 & our_kanji
    missing = top_1000 - our_kanji
    
    print("\n" + "=" * 50)
    print("=== TOP 1000 FREQUENCY COVERAGE ===")
    print(f"Covered: {len(covered)} / 1000 ({len(covered) / 10:.1f}%)")
    print(f"Missing: {len(missing)}")
    
    if missing:
        # Sort missing by frequency
        missing_with_freq = [(k, f) for k, f in freq_list if k in missing]
        missing_with_freq.sort(key=lambda x: x[1])
        
        print(f"\nMissing kanji (sorted by frequency, most common first):")
        for i, (k, f) in enumerate(missing_with_freq[:50]):
            info = external.get(k, {})
            meaning = ", ".join(info.get("meanings", [])[:2]) if info.get("meanings") else "?"
            jlpt = info.get("jlpt_new") or info.get("jlpt_old") or "?"
            print(f"  {i+1:3}. {k} (freq: {f:4}, JLPT: N{jlpt}, meaning: {meaning})")
        
        if len(missing_with_freq) > 50:
            print(f"  ... and {len(missing_with_freq) - 50} more")
        
        # Group by JLPT level
        print("\n--- Missing by JLPT level ---")
        jlpt_groups = {1: [], 2: [], 3: [], 4: [], 5: [], None: []}
        for k, f in missing_with_freq:
            info = external.get(k, {})
            jlpt = info.get("jlpt_new")
            if jlpt in jlpt_groups:
                jlpt_groups[jlpt].append(k)
            else:
                jlpt_groups[None].append(k)
        
        for level in [5, 4, 3, 2, 1, None]:
            count = len(jlpt_groups[level])
            if count > 0:
                label = f"N{level}" if level else "No JLPT"
                sample = "".join(jlpt_groups[level][:20])
                print(f"  {label}: {count} kanji - {sample}{'...' if count > 20 else ''}")
    else:
        print("\n✅ All top 1000 frequent kanji are in your deck!")
    
    return missing


def main():
    deck_data = add_missing_kanji()
    missing_freq = frequency_eda(deck_data)
    
    print("\n" + "=" * 50)
    print("Done!")


if __name__ == "__main__":
    main()

