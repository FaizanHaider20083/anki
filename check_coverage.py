#!/usr/bin/env python3
"""
Script to check JLPT vocabulary coverage across all Anki decks.
Scrapes word lists from japanesetest4you.com and identifies missing words.
Missing words are added to a new deck for review.
"""

import json
import requests
import re
import time
from bs4 import BeautifulSoup
from collections import defaultdict

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Vocabulary source - use cache file (faster, no 403 errors) or live scraping
VOCAB_CACHE_FILE = 'jlpt_vocabulary_cache.json'
USE_CACHE = True  # Set to False to scrape live (may get 403 errors)

# japanesetest4you.com URLs (for live scraping)
VOCAB_URLS = {
    'N5': 'https://japanesetest4you.com/jlpt-n5-vocabulary-list/',
    'N4': 'https://japanesetest4you.com/jlpt-n4-vocabulary-list/',
    'N3': 'https://japanesetest4you.com/jlpt-n3-vocabulary-list/',
    'N2': 'https://japanesetest4you.com/jlpt-n2-vocabulary-list/',
    'N1': 'https://japanesetest4you.com/jlpt-n1-vocabulary-list/',
}

# Configuration
LEVEL_TO_CHECK = 'N3'  # Change this to check different levels
MISSING_WORDS_DECK = f'JLPT_{LEVEL_TO_CHECK}_Missing'  # Deck for missing words

# Mode: 'check' for full coverage check, 'search' for searching scraped vocab
MODE = 'check'  # Change to 'search' to search the scraped vocabulary


def anki_request(action, **params):
    """Send request to AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post(ANKI_CONNECT_URL, data=request_json)
    response_data = response.json()
    
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    
    return response_data.get('result')


def get_all_decks():
    """Get all deck names from Anki."""
    return anki_request('deckNames')


def search_word_in_anki(word):
    """Search for a word across all Anki decks. Returns list of decks containing the word."""
    # Search in front field
    query = f'"front:*{word}*"'
    try:
        note_ids = anki_request('findNotes', query=query)
        if note_ids:
            # Get deck info for these notes
            notes_info = anki_request('notesInfo', notes=note_ids)
            decks = set()
            for note in notes_info:
                card_ids = note.get('cards', [])
                if card_ids:
                    cards_info = anki_request('cardsInfo', cards=card_ids)
                    for card in cards_info:
                        decks.add(card.get('deckName', 'Unknown'))
            return list(decks)
    except Exception as e:
        print(f"      ⚠️ Search error for '{word}': {e}")
    return []


def load_vocab_from_cache(level):
    """Load vocabulary from the cache JSON file."""
    import os
    
    cache_path = os.path.join(os.path.dirname(__file__), VOCAB_CACHE_FILE)
    
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Cache file not found: {cache_path}")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        all_vocab = json.load(f)
    
    if level not in all_vocab:
        raise ValueError(f"Level {level} not found in cache. Available: {list(all_vocab.keys())}")
    
    return all_vocab[level]


def scrape_vocab_live(level):
    """Scrape vocabulary list from japanesetest4you.com (live)."""
    url = VOCAB_URLS.get(level)
    if not url:
        raise ValueError(f"Unknown level: {level}")
    
    print(f"   Fetching {url}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    }
    
    try:
        # Use a session to handle cookies
        session = requests.Session()
        session.headers.update(headers)
        
        # First visit the homepage to get cookies
        time.sleep(1)
        session.get('https://japanesetest4you.com/', timeout=10)
        
        time.sleep(1)
        response = session.get(url, timeout=30)
        
        if response.status_code == 403:
            print("   ⚠️  Got 403, retrying with different approach...")
            time.sleep(2)
            # Try with simpler headers
            simple_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=simple_headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pattern to match vocabulary entries: word (reading): meaning
        vocab_pattern = re.compile(r'^(.+?)\s*\(([^)]+)\):\s*(.+)$')
        
        # Extract from text content (most comprehensive)
        text = soup.get_text()
        vocab_dict = {}
        
        for line in text.split('\n'):
            line = line.strip()
            match = vocab_pattern.match(line)
            if match:
                word, reading, meaning = match.groups()
                word = word.strip()
                # Filter out garbage (too long = probably not a word)
                if word and len(word) < 20 and word not in vocab_dict:
                    vocab_dict[word] = {
                        'word': word,
                        'reading': reading.strip(),
                        'meaning': meaning.strip()
                    }
        
        # Also extract from links (catches some the text method misses)
        for link in soup.find_all('a'):
            text = link.get_text(strip=True)
            match = vocab_pattern.match(text)
            if match:
                word, reading, meaning = match.groups()
                word = word.strip()
                if word and len(word) < 20 and word not in vocab_dict:
                    vocab_dict[word] = {
                        'word': word,
                        'reading': reading.strip(),
                        'meaning': meaning.strip()
                    }
        
        print(f"   ✅ Found {len(vocab_dict)} unique vocabulary entries")
        return list(vocab_dict.values())
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise


def scrape_vocab(level):
    """Get vocabulary - from cache or live scraping based on USE_CACHE setting."""
    if USE_CACHE:
        print(f"   Loading from cache file ({VOCAB_CACHE_FILE})...")
        vocab = load_vocab_from_cache(level)
        print(f"   ✅ Loaded {len(vocab)} vocabulary entries from cache")
        return vocab
    else:
        return scrape_vocab_live(level)


def ensure_deck_exists(deck_name):
    """Create deck if it doesn't exist."""
    decks = anki_request('deckNames')
    if deck_name not in decks:
        print(f"   Creating deck: {deck_name}")
        anki_request('createDeck', deck=deck_name)
    return True


def add_missing_word(deck_name, vocab, level):
    """Add a missing word to Anki."""
    # Format the back
    back = ""
    if vocab['reading']:
        back += f"({vocab['reading']})\n\n"
    back += vocab['meaning']
    back += f"\n\n━━━━━━━━━━━━━━━━━━━━\n"
    back += f"📚 Source: JLPT Sensei {level}"
    
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            'Front': vocab['word'],
            'Back': back
        },
        'tags': ['japanese', 'vocabulary', 'jlpt', level.lower(), 'missing-coverage'],
        'options': {
            'allowDuplicate': False,
            'duplicateScope': 'deck'
        }
    }
    
    try:
        anki_request('addNote', note=note)
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    """Main function to check vocabulary coverage."""
    print("=" * 70)
    print(f"📊 JLPT {LEVEL_TO_CHECK} Vocabulary Coverage Checker")
    print("=" * 70)
    print()
    
    # Check Anki connection
    print("1. Checking connection to Anki...")
    try:
        version = anki_request('version')
        print(f"   ✅ Connected to AnkiConnect (version {version})")
    except Exception as e:
        print(f"   ❌ Error: Could not connect to Anki.")
        print(f"   Make sure Anki is running with AnkiConnect add-on installed.")
        return
    
    # Get all existing decks
    print("\n2. Getting existing decks...")
    try:
        decks = get_all_decks()
        print(f"   ✅ Found {len(decks)} decks:")
        for deck in sorted(decks):
            if deck != 'Default':
                print(f"      • {deck}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Scrape vocabulary from japanesetest4you.com
    print(f"\n3. Scraping {LEVEL_TO_CHECK} vocabulary from japanesetest4you.com...")
    try:
        vocab_list = scrape_vocab(LEVEL_TO_CHECK)
    except Exception as e:
        print(f"   ❌ Error scraping: {e}")
        return
    
    if not vocab_list:
        print("   ⚠️ No vocabulary found. The website structure may have changed.")
        return
    
    # Check coverage
    print(f"\n4. Checking coverage against your Anki decks...")
    print("   This may take a few minutes...")
    print()
    
    found_words = []
    missing_words = []
    
    for i, vocab in enumerate(vocab_list, 1):
        word = vocab['word']
        
        # Progress indicator
        if i % 20 == 0 or i == len(vocab_list):
            print(f"   Progress: {i}/{len(vocab_list)} words checked...")
        
        # Search in Anki
        containing_decks = search_word_in_anki(word)
        
        if containing_decks:
            found_words.append({
                **vocab,
                'decks': containing_decks
            })
        else:
            missing_words.append(vocab)
    
    # Results summary
    print("\n" + "=" * 70)
    print("📊 COVERAGE REPORT")
    print("=" * 70)
    
    coverage_pct = (len(found_words) / len(vocab_list)) * 100 if vocab_list else 0
    
    print(f"\nTotal {LEVEL_TO_CHECK} vocabulary: {len(vocab_list)}")
    print(f"✅ Found in your decks: {len(found_words)} ({coverage_pct:.1f}%)")
    print(f"❌ Missing: {len(missing_words)} ({100-coverage_pct:.1f}%)")
    
    if missing_words:
        print(f"\n📝 Missing words preview (first 20):")
        for vocab in missing_words[:20]:
            reading = f" ({vocab['reading']})" if vocab['reading'] else ""
            meaning = vocab['meaning'][:40] + "..." if len(vocab['meaning']) > 40 else vocab['meaning']
            print(f"   • {vocab['word']}{reading}: {meaning}")
        
        if len(missing_words) > 20:
            print(f"   ... and {len(missing_words) - 20} more")
    
    # Offer to add missing words
    if missing_words:
        print("\n" + "=" * 70)
        print(f"Would you like to add {len(missing_words)} missing words to '{MISSING_WORDS_DECK}'?")
        print("=" * 70)
        
        choice = input("Continue? (yes/no/dry-run): ").strip().lower()
        
        if choice not in ['yes', 'y', 'dry-run', 'dry']:
            print("Cancelled. Missing words not added.")
            return
        
        dry_run = choice in ['dry-run', 'dry']
        
        print(f"\n5. {'[DRY RUN] ' if dry_run else ''}Adding missing words...")
        
        if not dry_run:
            ensure_deck_exists(MISSING_WORDS_DECK)
        
        added = 0
        errors = 0
        
        for i, vocab in enumerate(missing_words, 1):
            if dry_run:
                print(f"   📝 [{i}/{len(missing_words)}] Would add: {vocab['word']}")
                added += 1
            else:
                success, error = add_missing_word(MISSING_WORDS_DECK, vocab, LEVEL_TO_CHECK)
                if success:
                    print(f"   ✅ [{i}/{len(missing_words)}] Added: {vocab['word']}")
                    added += 1
                else:
                    print(f"   ❌ [{i}/{len(missing_words)}] Error: {vocab['word']} - {error}")
                    errors += 1
        
        print("\n" + "=" * 70)
        print("🎉 COMPLETE!")
        print("=" * 70)
        print(f"  ✅ Added: {added}")
        print(f"  ❌ Errors: {errors}")
        
        if dry_run:
            print("\n💡 This was a dry run. Run again with 'yes' to actually add cards.")
    else:
        print("\n🎉 Perfect coverage! All words are already in your decks!")


def search_mode():
    """Interactive search mode to verify scraped vocabulary."""
    print("=" * 70)
    print(f"🔍 JLPT {LEVEL_TO_CHECK} Vocabulary Search Mode")
    print("=" * 70)
    print("This mode lets you search the scraped vocabulary to verify accuracy.")
    print()
    
    # Scrape vocabulary
    print(f"1. Scraping {LEVEL_TO_CHECK} vocabulary from japanesetest4you.com...")
    try:
        vocab_list = scrape_vocab(LEVEL_TO_CHECK)
    except Exception as e:
        print(f"   ❌ Error scraping: {e}")
        return
    
    # Create lookup dictionaries
    by_word = {v['word']: v for v in vocab_list}
    by_reading = defaultdict(list)
    by_meaning = defaultdict(list)
    
    for v in vocab_list:
        by_reading[v['reading'].lower()].append(v)
        # Index by words in meaning
        for word in v['meaning'].lower().split():
            if len(word) > 2:
                by_meaning[word].append(v)
    
    print(f"\n✅ Loaded {len(vocab_list)} vocabulary entries")
    print(f"   Indexed by: word ({len(by_word)}), reading ({len(by_reading)}), meaning keywords ({len(by_meaning)})")
    
    # Show some stats
    print(f"\n📊 Quick Stats:")
    print(f"   First 5 words: {', '.join([v['word'] for v in vocab_list[:5]])}")
    print(f"   Last 5 words: {', '.join([v['word'] for v in vocab_list[-5:]])}")
    
    # Interactive search loop
    print("\n" + "=" * 70)
    print("Enter a search term (Japanese word, romaji, or English meaning)")
    print("Commands: 'stats', 'list [n]', 'quit'")
    print("=" * 70)
    
    while True:
        try:
            query = input("\n🔍 Search: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting search mode.")
            break
        
        if not query:
            continue
        
        if query.lower() == 'quit':
            print("Exiting search mode.")
            break
        
        if query.lower() == 'stats':
            print(f"\n📊 Vocabulary Statistics:")
            print(f"   Total entries: {len(vocab_list)}")
            print(f"   Unique words: {len(by_word)}")
            print(f"   Unique readings: {len(by_reading)}")
            continue
        
        if query.lower().startswith('list'):
            parts = query.split()
            n = int(parts[1]) if len(parts) > 1 else 20
            print(f"\n📋 First {n} entries:")
            for i, v in enumerate(vocab_list[:n], 1):
                print(f"   {i:4}. {v['word']} ({v['reading']}): {v['meaning'][:50]}")
            continue
        
        # Search
        results = []
        
        # Exact word match
        if query in by_word:
            results.append(('exact word', by_word[query]))
        
        # Partial word match
        for word, v in by_word.items():
            if query in word and v not in [r[1] for r in results]:
                results.append(('partial word', v))
        
        # Reading match
        query_lower = query.lower()
        if query_lower in by_reading:
            for v in by_reading[query_lower]:
                if v not in [r[1] for r in results]:
                    results.append(('reading', v))
        
        # Partial reading match
        for reading, vlist in by_reading.items():
            if query_lower in reading:
                for v in vlist:
                    if v not in [r[1] for r in results]:
                        results.append(('partial reading', v))
        
        # Meaning match
        if query_lower in by_meaning:
            for v in by_meaning[query_lower][:5]:  # Limit meaning matches
                if v not in [r[1] for r in results]:
                    results.append(('meaning', v))
        
        # Display results
        if results:
            print(f"\n✅ Found {len(results)} result(s):")
            for match_type, v in results[:15]:  # Limit display
                print(f"   [{match_type}] {v['word']} ({v['reading']}): {v['meaning']}")
            if len(results) > 15:
                print(f"   ... and {len(results) - 15} more")
        else:
            print(f"   ❌ No results for '{query}'")


if __name__ == '__main__':
    if MODE == 'search':
        search_mode()
    else:
        main()

