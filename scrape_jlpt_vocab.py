#!/usr/bin/env python3
"""
Scrape JLPT vocabulary for N3 and N2 and report overlaps.

Default source: japanesetest4you.com (public word bank).
Falls back to a local cache JSON if available to avoid 403 issues.

Outputs:
  - jlpt_vocab_N3.json
  - jlpt_vocab_N2.json
  - summary on stdout (counts, overlap)
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
LEVELS = ["N3", "N2"]  # scrape these levels

# Primary source URLs (japanesetest4you)
VOCAB_URLS = {
    "N5": "https://japanesetest4you.com/jlpt-n5-vocabulary-list/",
    "N4": "https://japanesetest4you.com/jlpt-n4-vocabulary-list/",
    "N3": "https://japanesetest4you.com/jlpt-n3-vocabulary-list/",
    "N2": "https://japanesetest4you.com/jlpt-n2-vocabulary-list/",
    "N1": "https://japanesetest4you.com/jlpt-n1-vocabulary-list/",
}

# Cache file to avoid repeated scraping / 403
VOCAB_CACHE_FILE = Path("jlpt_vocabulary_cache.json")
# Prefer cache by default to avoid blocks. Set to False to force live scrape.
USE_CACHE = True

# Minimum reasonable counts (sanity check)
MIN_EXPECTED = {
    "N3": 1500,  # we previously saw ~1693
    "N2": 1500,  # we previously saw ~1544
}

# Output files
OUT_DIR = Path(".")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def browser_headers() -> Dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }


def load_cache(level: str) -> List[Dict]:
    if not VOCAB_CACHE_FILE.exists():
        raise FileNotFoundError(f"Cache file not found: {VOCAB_CACHE_FILE}")
    data = json.loads(VOCAB_CACHE_FILE.read_text(encoding="utf-8"))
    if level not in data:
        raise ValueError(f"Level {level} not found in cache. Available: {list(data.keys())}")
    return data[level]


def parse_vocab_from_html(html: str) -> List[Dict]:
    """Extract vocab entries from the HTML page using multiple heuristics."""
    soup = BeautifulSoup(html, "html.parser")

    vocab_dict = {}

    # Patterns (loosened to handle en-dash, Japanese parens, missing colon)
    patterns = [
        re.compile(r"^(.+?)\s*[（(]([^)）]+)[)）]\s*[:：-]\s*(.+)$"),
        re.compile(r"^(.+?)\s*\(([^)]+)\)\s*[:：-]\s*(.+)$"),
        re.compile(r"^(.+?)\s*[:：-]\s*(.+)$"),  # no reading available
    ]

    def try_add(word, reading, meaning):
        word = (word or "").strip()
        if not word or len(word) > 64:
            return
        if reading is None:
            reading = ""
        meaning = (meaning or "").strip()
        vocab_dict[word] = {
            "word": word,
            "reading": reading.strip(),
            "meaning": meaning,
        }

    # From text lines
    for line in soup.get_text().split("\n"):
        line = line.strip()
        if not line:
            continue
        for pat in patterns:
            m = pat.match(line)
            if m:
                if len(m.groups()) == 3:
                    w, r, me = m.groups()
                else:
                    w, me = m.groups()
                    r = ""
                try_add(w, r, me)
                break

    # From links (flashcard anchors)
    for link in soup.find_all("a"):
        text = link.get_text(strip=True)
        if not text:
            continue
        for pat in patterns:
            m = pat.match(text)
            if m:
                if len(m.groups()) == 3:
                    w, r, me = m.groups()
                else:
                    w, me = m.groups()
                    r = ""
                try_add(w, r, me)
                break

    return list(vocab_dict.values())


def scrape_level(level: str) -> List[Dict]:
    """Scrape a single level (live)."""
    url = VOCAB_URLS[level]
    print(f"   Fetching {url} ...")

    session = requests.Session()
    session.headers.update(browser_headers())

    # Warm-up to get cookies
    session.get("https://japanesetest4you.com/", timeout=10)
    time.sleep(0.5)

    resp = session.get(url, timeout=30)
    if resp.status_code == 403:
        print("   ⚠️  403 received, retrying with simpler headers...")
        simple_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        resp = requests.get(url, headers=simple_headers, timeout=30)

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} for {url}")

    vocab = parse_vocab_from_html(resp.text)
    if len(vocab) == 0:
        print("   ⚠️  Parsed 0 entries. Writing debug preview to scrape_debug.html")
        Path("scrape_debug.html").write_text(resp.text, encoding="utf-8")
    else:
        print(f"   ✅ Parsed {len(vocab)} entries")

    # Sanity check: if below expected threshold, treat as failed
    min_expected = MIN_EXPECTED.get(level, 0)
    if min_expected and len(vocab) < min_expected:
        raise RuntimeError(
            f"Parsed only {len(vocab)} entries for {level}, expected at least {min_expected}"
        )

    return vocab


def get_vocab(level: str) -> List[Dict]:
    # Try cache first if enabled
    if USE_CACHE and VOCAB_CACHE_FILE.exists():
        print(f"   Loading {level} from cache {VOCAB_CACHE_FILE} ...")
        try:
            vocab = load_cache(level)
            print(f"   ✅ Loaded {len(vocab)} entries from cache")
            return vocab
        except Exception as e:
            print(f"   ⚠️  Cache load failed: {e}")

    # Fall back to live scrape
    return scrape_level(level)


def save_vocab(level: str, vocab: List[Dict]):
    out_path = OUT_DIR / f"jlpt_vocab_{level}.json"
    out_path.write_text(json.dumps(vocab, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   💾 Saved {len(vocab)} entries to {out_path}")


def main():
    print("=" * 70)
    print("🈶 JLPT N3/N2 Vocabulary Scraper")
    print("=" * 70)
    print(f"Levels: {', '.join(LEVELS)}")
    print(f"Using cache: {USE_CACHE}")
    print()

    vocab_by_level = {}

    for lvl in LEVELS:
        print(f"\n--- {lvl} ---")
        try:
            vocab = get_vocab(lvl)
            vocab_by_level[lvl] = vocab
            save_vocab(lvl, vocab)
        except Exception as e:
            print(f"   ❌ Failed to fetch {lvl}: {e}")
            # Try cache as fallback if live failed and cache exists
            if VOCAB_CACHE_FILE.exists():
                try:
                    vocab = load_cache(lvl)
                    vocab_by_level[lvl] = vocab
                    print(f"   ✅ Fallback to cache: loaded {len(vocab)} entries for {lvl}")
                    save_vocab(lvl, vocab)
                except Exception as e2:
                    print(f"   ❌ Fallback cache load failed for {lvl}: {e2}")

    if "N2" in vocab_by_level and "N3" in vocab_by_level:
        n2_words = {v["word"] for v in vocab_by_level["N2"]}
        n3_words = {v["word"] for v in vocab_by_level["N3"]}
        overlap = n3_words & n2_words
        missing_in_n2 = n3_words - n2_words

        print("\n" + "=" * 70)
        print("📊 Coverage Check (Is N3 ⊆ N2?)")
        print("=" * 70)
        print(f"N3 count: {len(n3_words)}")
        print(f"N2 count: {len(n2_words)}")
        print(f"Overlap (N3 in N2): {len(overlap)}")
        print(f"N3 missing from N2: {len(missing_in_n2)}")
        if missing_in_n2:
            sample = list(missing_in_n2)[:10]
            print(f"   Sample missing from N2: {sample}")


if __name__ == "__main__":
    main()

