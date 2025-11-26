#!/usr/bin/env python3
"""
Enrich vocab_samples in kanji_deck_data_filled.json with readings and meanings.

Uses n2.csv, n3.csv, n4.csv, n5.csv as sources.
Falls back to Jisho API for words not found in CSVs.
"""

import csv
import json
import re
import time
import requests
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parent

# Input/Output
DECK_JSON = ROOT / "kanji_deck_data_filled.json"
OUTPUT_JSON = ROOT / "kanji_deck_data_enriched.json"

# Vocab CSV sources
VOCAB_CSVS = [
    ROOT / "niai data/data/n3.csv",
    ROOT / "niai data/data/n2.csv",
    ROOT / "niai data/data/n4.csv",
    ROOT / "niai data/data/n5.csv",
]

# Use Jisho API for missing words (slower but complete)
USE_JISHO_FALLBACK = True
JISHO_DELAY = 0.5  # seconds between requests


def load_vocab_lookup() -> Dict[str, Dict[str, str]]:
    """Build lookup table: word -> {reading, meaning}"""
    lookup = {}
    
    for csv_path in VOCAB_CSVS:
        if not csv_path.exists():
            print(f"  ⚠️  Not found: {csv_path}")
            continue
        
        count = 0
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                word = row.get("expression", "").strip()
                reading = row.get("reading", "").strip()
                meaning = row.get("meaning", "").strip()
                
                if word and word not in lookup:
                    lookup[word] = {"reading": reading, "meaning": meaning}
                    count += 1
        
        print(f"  ✓ Loaded {count} words from {csv_path.name}")
    
    return lookup


def lookup_jisho(word: str) -> Optional[Dict[str, str]]:
    """Look up word on Jisho API."""
    try:
        # Clean word (remove ~ prefix, etc.)
        clean_word = word.lstrip("~～")
        
        url = f"https://jisho.org/api/v1/search/words?keyword={clean_word}"
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        results = data.get("data", [])
        
        if not results:
            return None
        
        # Find best match
        for result in results:
            japanese = result.get("japanese", [])
            senses = result.get("senses", [])
            
            for jp in japanese:
                word_match = jp.get("word", "") or jp.get("reading", "")
                if word_match == clean_word or jp.get("reading", "") == clean_word:
                    reading = jp.get("reading", "")
                    
                    # Get first English meaning
                    meaning = ""
                    if senses:
                        eng_defs = senses[0].get("english_definitions", [])
                        if eng_defs:
                            meaning = ", ".join(eng_defs[:3])
                    
                    return {"reading": reading, "meaning": meaning}
        
        # If no exact match, use first result
        if results:
            jp = results[0].get("japanese", [{}])[0]
            reading = jp.get("reading", "")
            meaning = ""
            senses = results[0].get("senses", [])
            if senses:
                eng_defs = senses[0].get("english_definitions", [])
                if eng_defs:
                    meaning = ", ".join(eng_defs[:3])
            return {"reading": reading, "meaning": meaning}
        
        return None
    except Exception as e:
        return None


def enrich_vocab_sample(word: str, lookup: Dict, jisho_cache: Dict) -> str:
    """Enrich a single vocab sample with reading and meaning."""
    # Clean the word for lookup
    clean_word = word.lstrip("~～").rstrip("～~")
    
    # Remove any existing formatting (e.g., "word (reading)")
    if "(" in clean_word:
        clean_word = clean_word.split("(")[0].strip()
    
    # Check lookup table
    info = lookup.get(clean_word) or lookup.get(word)
    
    # Try Jisho if not found
    if not info and USE_JISHO_FALLBACK:
        if clean_word in jisho_cache:
            info = jisho_cache[clean_word]
        else:
            info = lookup_jisho(clean_word)
            jisho_cache[clean_word] = info
            if info:
                time.sleep(JISHO_DELAY)
    
    if info:
        reading = info.get("reading", "")
        meaning = info.get("meaning", "")
        
        if reading and meaning:
            return f"{word} ({reading}) - {meaning}"
        elif reading:
            return f"{word} ({reading})"
        elif meaning:
            return f"{word} - {meaning}"
    
    return word  # Return unchanged if no info found


def main():
    print("=" * 60)
    print("📚 Vocab Sample Enrichment Tool")
    print("=" * 60)
    
    # Load lookup table from CSVs
    print("\n1. Loading vocabulary from CSVs...")
    lookup = load_vocab_lookup()
    print(f"   Total: {len(lookup)} unique words in lookup table")
    
    # Load deck JSON
    print(f"\n2. Loading {DECK_JSON.name}...")
    data = json.loads(DECK_JSON.read_text(encoding="utf-8"))
    print(f"   ✓ Loaded {len(data)} kanji entries")
    
    # Count vocab samples that need enrichment
    total_samples = 0
    samples_need_enrichment = 0
    for entry in data:
        samples = entry.get("vocab_samples", [])
        for s in samples:
            total_samples += 1
            if isinstance(s, str) and " - " not in s and "(" not in s:
                samples_need_enrichment += 1
    
    print(f"   Total vocab samples: {total_samples}")
    print(f"   Need enrichment: {samples_need_enrichment}")
    
    # Enrich
    print("\n3. Enriching vocab samples...")
    jisho_cache = {}
    enriched_count = 0
    jisho_lookups = 0
    
    for i, entry in enumerate(data):
        samples = entry.get("vocab_samples", [])
        new_samples = []
        
        for s in samples:
            if isinstance(s, str):
                enriched = enrich_vocab_sample(s, lookup, jisho_cache)
                new_samples.append(enriched)
                if enriched != s:
                    enriched_count += 1
            else:
                new_samples.append(s)
        
        entry["vocab_samples"] = new_samples
        
        # Progress
        if (i + 1) % 200 == 0:
            print(f"   Progress: {i + 1}/{len(data)} entries, {enriched_count} samples enriched, {len(jisho_cache)} Jisho lookups")
    
    print(f"\n   ✓ Enriched {enriched_count} vocab samples")
    print(f"   ✓ Jisho lookups: {len(jisho_cache)}")
    
    # Save
    print(f"\n4. Saving to {OUTPUT_JSON.name}...")
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   ✓ Saved!")
    
    # Also update the original file
    print(f"\n5. Updating {DECK_JSON.name}...")
    DECK_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   ✓ Updated!")
    
    print("\n" + "=" * 60)
    print("✅ Done!")
    print("=" * 60)


if __name__ == "__main__":
    main()

