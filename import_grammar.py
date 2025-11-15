#!/usr/bin/env python3
"""
Script to import JLPT grammar patterns from CSV into Anki.
Creates cards with grammar pattern on front, meaning/romaji on back.
"""

import csv
import json
import requests
from collections import defaultdict

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Deck configuration - choose which levels to import
LEVELS_TO_IMPORT = ['N2', 'N3']  # Change this to import different levels
DECK_PREFIX = 'JLPT_Grammar'     # Cards go to JLPT_Grammar::N2, JLPT_Grammar::N3, etc.

# CSV file
CSV_FILE = 'JLPTgrammar.csv'


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


def parse_grammar_csv(filepath):
    """Parse the grammar CSV file and return entries grouped by level."""
    entries = defaultdict(list)
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        
        for row in reader:
            if len(row) < 5:
                continue
            
            level = row[0].strip()      # N5, N4, N3, N2, N1
            number = row[1].strip()     # Pattern number
            japanese = row[2].strip()   # Grammar pattern in Japanese
            romaji = row[3].strip()     # Romaji reading
            meaning = row[4].strip()    # English meaning
            
            # Skip header rows or invalid entries
            if not level.startswith('N') or not japanese:
                continue
            
            entries[level].append({
                'number': number,
                'japanese': japanese,
                'romaji': romaji,
                'meaning': meaning,
                'level': level
            })
    
    return entries


def format_card_back(entry):
    """Format the back of the grammar card."""
    back = f"【{entry['romaji']}】\n\n"
    back += f"{entry['meaning']}\n\n"
    back += f"━━━━━━━━━━━━━━━━━━━━\n"
    back += f"📚 {entry['level']} Grammar #{entry['number']}"
    return back


def add_grammar_card(deck_name, entry):
    """Add a grammar card to Anki."""
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            'Front': entry['japanese'],
            'Back': format_card_back(entry)
        },
        'tags': ['japanese', 'grammar', 'jlpt', entry['level'].lower()],
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
    print("📖 JLPT Grammar Importer")
    print("=" * 70)
    print(f"CSV File: {CSV_FILE}")
    print(f"Levels to import: {', '.join(LEVELS_TO_IMPORT)}")
    print()
    
    # Check Anki connection
    print("1. Checking connection to Anki...")
    try:
        version = anki_request('version')
        print(f"   ✅ Connected to AnkiConnect (version {version})")
    except Exception as e:
        print(f"   ❌ Error: Could not connect to Anki.")
        print(f"   Make sure Anki is running with AnkiConnect add-on installed.")
        print(f"   Error: {e}")
        return
    
    # Parse CSV
    print(f"\n2. Parsing {CSV_FILE}...")
    try:
        all_entries = parse_grammar_csv(CSV_FILE)
        print(f"   ✅ Found grammar patterns:")
        for level in sorted(all_entries.keys()):
            count = len(all_entries[level])
            marker = "→ Will import" if level in LEVELS_TO_IMPORT else "  (skipping)"
            print(f"      {level}: {count} patterns {marker}")
    except FileNotFoundError:
        print(f"   ❌ Error: {CSV_FILE} not found")
        return
    except Exception as e:
        print(f"   ❌ Error parsing CSV: {e}")
        return
    
    # Filter to requested levels
    entries_to_import = {level: all_entries[level] for level in LEVELS_TO_IMPORT if level in all_entries}
    total_entries = sum(len(v) for v in entries_to_import.values())
    
    if not entries_to_import:
        print(f"\n   ⚠️ No entries found for levels: {LEVELS_TO_IMPORT}")
        return
    
    # Confirmation
    print("\n" + "=" * 70)
    print("⚠️  Ready to import grammar cards!")
    print("=" * 70)
    print(f"Total patterns to import: {total_entries}")
    for level, entries in entries_to_import.items():
        deck_name = f"{DECK_PREFIX}::{level}"
        print(f"  • {level}: {len(entries)} patterns → {deck_name}")
    print()
    
    choice = input("Continue? (yes/no/dry-run): ").strip().lower()
    
    if choice not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        return
    
    dry_run = choice in ['dry-run', 'dry']
    
    # Process each level
    print(f"\n3. {'[DRY RUN] ' if dry_run else ''}Importing grammar cards...")
    print("=" * 70)
    
    stats = {'added': 0, 'skipped': 0, 'errors': 0}
    
    for level in LEVELS_TO_IMPORT:
        if level not in entries_to_import:
            continue
        
        entries = entries_to_import[level]
        deck_name = f"{DECK_PREFIX}::{level}"
        
        print(f"\n📚 {level} ({len(entries)} patterns) → {deck_name}")
        
        if not dry_run:
            ensure_deck_exists(deck_name)
        
        for i, entry in enumerate(entries, 1):
            # Check for duplicates
            if not dry_run and card_exists(deck_name, entry['japanese']):
                print(f"   ⏭️  [{i}/{len(entries)}] Already exists: {entry['japanese'][:30]}")
                stats['skipped'] += 1
                continue
            
            if dry_run:
                print(f"   📝 [{i}/{len(entries)}] Would add: {entry['japanese'][:40]}...")
                stats['added'] += 1
            else:
                success, error = add_grammar_card(deck_name, entry)
                if success:
                    print(f"   ✅ [{i}/{len(entries)}] Added: {entry['japanese'][:40]}...")
                    stats['added'] += 1
                else:
                    print(f"   ❌ [{i}/{len(entries)}] Error: {entry['japanese'][:30]} - {error}")
                    stats['errors'] += 1
    
    # Summary
    print("\n" + "=" * 70)
    print("🎉 IMPORT COMPLETE!")
    print("=" * 70)
    print(f"  ✅ Added: {stats['added']}")
    print(f"  ⏭️  Skipped (duplicates): {stats['skipped']}")
    print(f"  ❌ Errors: {stats['errors']}")
    print("=" * 70)
    
    if dry_run:
        print("\n💡 This was a dry run. No cards were actually added.")
        print("   Run again and choose 'yes' to import.")


if __name__ == '__main__':
    main()



