#!/usr/bin/env python3
"""
Create Anki deck from kanji_deck_data_filled.json

Card format:
- Front: The kanji character (large)
- Back: Formatted with meaning, readings, vocab samples, and similar kanji
"""

import json
import requests
from pathlib import Path
from typing import List, Dict

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Configuration
DECK_NAME = 'Kanji'
DECK_JSON = Path(__file__).resolve().parent / "kanji_deck_data_filled.json"

# Set to True to preview without making changes
DRY_RUN = False

# How many cards to process (set to None for all)
LIMIT = None  # e.g., 10 for testing


def anki_request(action: str, **params):
    """Send request to AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post(ANKI_CONNECT_URL, data=request_json)
    response_data = response.json()
    
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    
    return response_data.get('result')


def ensure_deck_exists(deck_name: str):
    """Create deck if it doesn't exist."""
    existing = anki_request('deckNames')
    if deck_name not in existing:
        anki_request('createDeck', deck=deck_name)
        print(f"  ✓ Created deck: {deck_name}")
    else:
        print(f"  ✓ Deck exists: {deck_name}")


def format_back(entry: Dict) -> str:
    """Format the back of the card with all information."""
    lines = []
    
    # Meaning (prominent)
    meaning = entry.get("meaning", "")
    if meaning:
        lines.append(f"<div style='font-size: 1.4em; font-weight: bold; color: #2c3e50; margin-bottom: 15px;'>{meaning}</div>")
    else:
        lines.append("<div style='font-size: 1.2em; color: #999; margin-bottom: 15px;'><i>(meaning unknown)</i></div>")
    
    # Readings section
    kunyomi = entry.get("kunyomi", "")
    onyomi = entry.get("onyomi", "")
    
    if kunyomi or onyomi:
        lines.append("<div style='margin-bottom: 15px;'>")
        if kunyomi:
            lines.append(f"<div><span style='color: #27ae60; font-weight: bold;'>訓読み:</span> {kunyomi}</div>")
        if onyomi:
            lines.append(f"<div><span style='color: #e74c3c; font-weight: bold;'>音読み:</span> {onyomi}</div>")
        lines.append("</div>")
    
    # Separator
    lines.append("<hr style='border: none; border-top: 1px solid #ddd; margin: 15px 0;'>")
    
    # Vocabulary samples
    vocab = entry.get("vocab_samples", [])
    if vocab:
        lines.append("<div style='margin-bottom: 15px;'>")
        lines.append("<div style='font-weight: bold; color: #8e44ad; margin-bottom: 8px;'>📚 Vocabulary:</div>")
        lines.append("<div style='padding-left: 10px;'>")
        for v in vocab[:4]:
            if isinstance(v, str):
                lines.append(f"<div style='margin: 3px 0;'>• {v}</div>")
            elif isinstance(v, dict):
                word = v.get("word", "")
                meaning = v.get("meaning", "")
                lines.append(f"<div style='margin: 3px 0;'>• {word} - {meaning}</div>")
        lines.append("</div></div>")
    
    # Similar kanji
    similar = entry.get("similar", [])
    if similar:
        lines.append("<div style='margin-top: 15px;'>")
        lines.append("<div style='font-weight: bold; color: #f39c12; margin-bottom: 8px;'>👁️ Similar Kanji:</div>")
        lines.append("<div style='padding-left: 10px; display: flex; flex-wrap: wrap; gap: 10px;'>")
        for s in similar[:4]:
            if isinstance(s, dict):
                sk = s.get("kanji", "")
                sm = s.get("meaning", "")
                if sk:
                    lines.append(f"<div style='background: #e8e8e8; padding: 5px 10px; border-radius: 5px; border: 1px solid #ccc;'><span style='font-size: 1.3em; color: #000;'>{sk}</span> <span style='color: #333;'>({sm})</span></div>")
        lines.append("</div></div>")
    
    return "\n".join(lines)


def format_front(kanji: str) -> str:
    """Format the front of the card (just the kanji, large)."""
    return f"<div style='font-size: 4em; text-align: center;'>{kanji}</div>"


def card_exists(deck_name: str, kanji: str) -> bool:
    """Check if a card with this kanji already exists in the deck."""
    query = f'"deck:{deck_name}" "front:*{kanji}*"'
    try:
        note_ids = anki_request('findNotes', query=query)
        return len(note_ids) > 0
    except:
        return False


def add_card(entry: Dict) -> tuple:
    """Add a single card to Anki."""
    kanji = entry.get("kanji", "")
    if not kanji:
        return False, "No kanji field"
    
    front = format_front(kanji)
    back = format_back(entry)
    
    note = {
        'deckName': DECK_NAME,
        'modelName': 'Basic',
        'fields': {
            'Front': front,
            'Back': back
        },
        'tags': ['kanji', 'jlpt', 'auto-generated'],
        'options': {
            'allowDuplicate': False,
            'duplicateScope': 'deck',
            'duplicateScopeOptions': {
                'deckName': DECK_NAME,
                'checkChildren': False
            }
        }
    }
    
    if DRY_RUN:
        return True, "Would add (dry run)"
    
    try:
        anki_request('addNote', note=note)
        return True, None
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("🀄 Kanji Deck Creator")
    print("=" * 60)
    
    # Load data
    print(f"\n1. Loading data from {DECK_JSON.name}...")
    data = json.loads(DECK_JSON.read_text(encoding="utf-8"))
    print(f"   ✓ Loaded {len(data)} kanji entries")
    
    if LIMIT:
        data = data[:LIMIT]
        print(f"   ⚠️  Limited to first {LIMIT} entries (testing mode)")
    
    # Check Anki connection
    print("\n2. Connecting to Anki...")
    try:
        version = anki_request('version')
        print(f"   ✓ Connected to AnkiConnect v{version}")
    except Exception as e:
        print(f"   ❌ Failed to connect to Anki!")
        print(f"   Make sure Anki is running with AnkiConnect installed.")
        print(f"   Error: {e}")
        return
    
    # Create deck
    print(f"\n3. Ensuring deck '{DECK_NAME}' exists...")
    if not DRY_RUN:
        ensure_deck_exists(DECK_NAME)
    else:
        print(f"   [DRY RUN] Would create/check deck: {DECK_NAME}")
    
    # Preview first card
    print("\n4. Preview of first card:")
    print("-" * 60)
    sample = data[0]
    print(f"Front: {sample['kanji']}")
    print(f"Back preview:")
    print(f"  Meaning: {sample.get('meaning', '(none)')}")
    print(f"  Kunyomi: {sample.get('kunyomi', '(none)')}")
    print(f"  Onyomi: {sample.get('onyomi', '(none)')}")
    print(f"  Vocab: {sample.get('vocab_samples', [])[:2]}...")
    print(f"  Similar: {[s.get('kanji') for s in sample.get('similar', [])[:3]]}...")
    print("-" * 60)
    
    # Confirm
    if DRY_RUN:
        print("\n🔍 DRY RUN MODE - No changes will be made")
    else:
        print(f"\n⚠️  About to add {len(data)} cards to deck '{DECK_NAME}'")
        confirm = input("Continue? (yes/no): ").strip().lower()
        if confirm not in ['yes', 'y']:
            print("Cancelled.")
            return
    
    # Add cards
    print(f"\n5. {'[DRY RUN] ' if DRY_RUN else ''}Adding cards...")
    
    success = 0
    skipped = 0
    errors = []
    
    for i, entry in enumerate(data):
        kanji = entry.get("kanji", "?")
        ok, err = add_card(entry)
        
        if ok:
            success += 1
        elif err and "duplicate" in err.lower():
            skipped += 1
        else:
            errors.append((kanji, err))
        
        # Progress
        if (i + 1) % 100 == 0 or i == len(data) - 1:
            print(f"   Progress: {i + 1}/{len(data)} (✓ {success}, ⏭️ {skipped}, ❌ {len(errors)})")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"✓ Added: {success}")
    print(f"⏭️ Skipped (duplicate): {skipped}")
    print(f"❌ Errors: {len(errors)}")
    
    if errors:
        print("\nFirst 10 errors:")
        for kanji, err in errors[:10]:
            print(f"  {kanji}: {err}")
    
    if not DRY_RUN and success > 0:
        print(f"\n✅ Done! Added {success} kanji cards to deck '{DECK_NAME}'")
        print("   Open Anki to sync and start studying!")


if __name__ == "__main__":
    main()

