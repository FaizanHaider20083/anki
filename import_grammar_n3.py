#!/usr/bin/env python3
"""
Script to import N3 grammar patterns from grammarN3.txt into Anki.
Format: "number. pattern - meaning - example"

Cards will have:
- Front: Grammar pattern
- Back: Meaning + Example
"""

import re
import json
import requests

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Configuration
GRAMMAR_FILE = 'grammarN3.txt'
DECK_NAME = 'JLPT_N3_Grammar'


def anki_request(action, **params):
    """Send request to AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post(ANKI_CONNECT_URL, data=request_json)
    response_data = response.json()
    
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    
    return response_data.get('result')


def ensure_deck_exists(deck_name):
    """Create deck if it doesn't exist."""
    decks = anki_request('deckNames')
    if deck_name not in decks:
        print(f"   Creating deck: {deck_name}")
        anki_request('createDeck', deck=deck_name)
    return True


def card_exists(deck_name, front_text):
    """Check if a card with the given front text already exists."""
    query = f'"deck:{deck_name}" "front:{front_text}"'
    note_ids = anki_request('findNotes', query=query)
    return len(note_ids) > 0


def parse_grammar_file(filepath):
    """Parse the grammar file and return list of entries."""
    entries = []
    
    # Multiple patterns to handle format variations
    # Standard: "1. ~ Sei - ~'s fault - example"
    pattern1 = re.compile(r'^(\d+)\.\s*(.+?)\s*-\s*(.+?)\s*-\s*(.+)$')
    # Missing dot: "60 ~1 tabi ni ~2 - meaning - example"
    pattern2 = re.compile(r'^(\d+)\s+(.+?)\s*-\s*(.+?)\s*-\s*(.+)$')
    # Using = instead of -: "109. pattern = meaning - example"
    pattern3 = re.compile(r'^(\d+)\.\s*(.+?)\s*[=-]\s*(.+?)\s*-\s*(.+)$')
    # Only two parts (missing meaning or example): "108. pattern - rest"
    pattern4 = re.compile(r'^(\d+)\.\s*(.+?)\s*-\s*(.+)$')
    # Missing dot AND only one dash: "60 pattern - example"
    pattern5 = re.compile(r'^(\d+)\s+(.+?)\s*-\s*(.+)$')
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            entry = None
            
            # Try pattern 1 (standard)
            match = pattern1.match(line)
            if match:
                num, pattern, meaning, example = match.groups()
                entry = {
                    'number': int(num),
                    'pattern': pattern.strip(),
                    'meaning': meaning.strip(),
                    'example': example.strip()
                }
            
            # Try pattern 2 (missing dot)
            if not entry:
                match = pattern2.match(line)
                if match:
                    num, pattern, meaning, example = match.groups()
                    entry = {
                        'number': int(num),
                        'pattern': pattern.strip(),
                        'meaning': meaning.strip(),
                        'example': example.strip()
                    }
            
            # Try pattern 3 (= instead of -)
            if not entry:
                match = pattern3.match(line)
                if match:
                    num, pattern, meaning, example = match.groups()
                    entry = {
                        'number': int(num),
                        'pattern': pattern.strip(),
                        'meaning': meaning.strip(),
                        'example': example.strip()
                    }
            
            # Try pattern 4 (only two parts - treat second as example)
            if not entry:
                match = pattern4.match(line)
                if match:
                    num, pattern, rest = match.groups()
                    entry = {
                        'number': int(num),
                        'pattern': pattern.strip(),
                        'meaning': '(see example)',
                        'example': rest.strip()
                    }
            
            # Try pattern 5 (missing dot AND only one dash)
            if not entry:
                match = pattern5.match(line)
                if match:
                    num, pattern, rest = match.groups()
                    entry = {
                        'number': int(num),
                        'pattern': pattern.strip(),
                        'meaning': '(see example)',
                        'example': rest.strip()
                    }
            
            if entry:
                entries.append(entry)
            else:
                print(f"   ⚠️ Could not parse line {line_num}: {line[:50]}...")
    
    return entries


def format_card_back(entry):
    """Format the back of the grammar card."""
    back = f"📖 Meaning:\n{entry['meaning']}\n\n"
    back += f"📝 Example:\n{entry['example']}\n\n"
    back += f"━━━━━━━━━━━━━━━━━━━━\n"
    back += f"📚 N3 Grammar #{entry['number']}"
    return back


def add_grammar_card(deck_name, entry):
    """Add a grammar card to Anki."""
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            'Front': entry['pattern'],
            'Back': format_card_back(entry)
        },
        'tags': ['japanese', 'grammar', 'jlpt', 'n3'],
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
    """Main function to import grammar patterns."""
    print("=" * 70)
    print("📖 N3 Grammar Importer")
    print("=" * 70)
    print(f"Source: {GRAMMAR_FILE}")
    print(f"Target deck: {DECK_NAME}")
    print()
    
    # Parse the grammar file
    print("1. Parsing grammar file...")
    try:
        entries = parse_grammar_file(GRAMMAR_FILE)
        print(f"   ✅ Parsed {len(entries)} grammar patterns")
    except FileNotFoundError:
        print(f"   ❌ File not found: {GRAMMAR_FILE}")
        return
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return
    
    # Show preview
    print("\n2. Preview (first 5 entries):")
    for entry in entries[:5]:
        print(f"   #{entry['number']}: {entry['pattern']}")
        print(f"      → {entry['meaning'][:40]}...")
    
    # Check Anki connection
    print("\n3. Checking connection to Anki...")
    try:
        version = anki_request('version')
        print(f"   ✅ Connected to AnkiConnect (version {version})")
    except Exception as e:
        print(f"   ❌ Error: Could not connect to Anki.")
        print(f"   Make sure Anki is running with AnkiConnect add-on installed.")
        return
    
    # Confirmation
    print("\n" + "=" * 70)
    print(f"Ready to import {len(entries)} grammar patterns to '{DECK_NAME}'")
    print("=" * 70)
    
    choice = input("Continue? (yes/no/dry-run): ").strip().lower()
    
    if choice not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        return
    
    dry_run = choice in ['dry-run', 'dry']
    
    # Create deck and add cards
    print(f"\n4. {'[DRY RUN] ' if dry_run else ''}Importing grammar cards...")
    
    if not dry_run:
        ensure_deck_exists(DECK_NAME)
    
    stats = {'added': 0, 'skipped': 0, 'errors': 0}
    
    for entry in entries:
        # Check for duplicates
        if not dry_run and card_exists(DECK_NAME, entry['pattern']):
            print(f"   ⏭️ #{entry['number']}: Already exists - {entry['pattern']}")
            stats['skipped'] += 1
            continue
        
        if dry_run:
            print(f"   📝 #{entry['number']}: Would add - {entry['pattern']}")
            stats['added'] += 1
        else:
            success, error = add_grammar_card(DECK_NAME, entry)
            if success:
                print(f"   ✅ #{entry['number']}: Added - {entry['pattern']}")
                stats['added'] += 1
            else:
                print(f"   ❌ #{entry['number']}: Error - {entry['pattern']} ({error})")
                stats['errors'] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 IMPORT COMPLETE!")
    print("=" * 70)
    print(f"  ✅ Added: {stats['added']}")
    print(f"  ⏭️ Skipped (duplicates): {stats['skipped']}")
    print(f"  ❌ Errors: {stats['errors']}")
    print("=" * 70)
    
    if dry_run:
        print("\n💡 This was a dry run. Run again with 'yes' to actually import.")


if __name__ == '__main__':
    main()

