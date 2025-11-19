#!/usr/bin/env python3
"""
Script to enrich existing Anki cards with kanji breakdowns.
Adds detailed kanji information (meanings, readings) to card backs.
"""

import json
import requests
import re

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Test with single deck first
TEST_DECK = 'n3_tn_ch9'

def anki_request(action, **params):
    """Send request to AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post(ANKI_CONNECT_URL, data=request_json)
    response_data = response.json()
    
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    
    return response_data.get('result')

def is_kanji(char):
    """Check if a character is kanji."""
    # Kanji unicode ranges
    return (
        '\u4e00' <= char <= '\u9fff' or  # CJK Unified Ideographs
        '\u3400' <= char <= '\u4dbf' or  # CJK Extension A
        '\U00020000' <= char <= '\U0002a6df'  # CJK Extension B
    )

def extract_kanji(text):
    """Extract all kanji characters from text."""
    return [char for char in text if is_kanji(char)]

def get_kanji_info(kanji):
    """Get detailed information about a kanji character.
    
    Uses the Kanjiapi.dev free API for kanji information.
    """
    try:
        url = f"https://kanjiapi.dev/v1/kanji/{kanji}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract relevant information
            meanings = data.get('meanings', [])
            kun_readings = data.get('kun_readings', [])
            on_readings = data.get('on_readings', [])
            grade = data.get('grade', 'N/A')
            stroke_count = data.get('stroke_count', 'N/A')
            
            return {
                'kanji': kanji,
                'meanings': meanings,
                'kun_readings': kun_readings,
                'on_readings': on_readings,
                'grade': grade,
                'stroke_count': stroke_count
            }
        else:
            return None
    except Exception as e:
        print(f"   ⚠️  Error fetching kanji info for {kanji}: {e}")
        return None

def format_kanji_breakdown(kanji_list):
    """Format kanji information into readable text for card back."""
    if not kanji_list:
        return ""
    
    breakdown = "\n\n━━━━━━━━━━━━━━━━━━━━\n"
    breakdown += "📖 Kanji Breakdown:\n"
    breakdown += "━━━━━━━━━━━━━━━━━━━━\n"
    
    for kanji_info in kanji_list:
        if not kanji_info:
            continue
            
        kanji = kanji_info['kanji']
        meanings = ', '.join(kanji_info['meanings'][:3])  # Top 3 meanings
        kun = ', '.join(kanji_info['kun_readings'][:2]) if kanji_info['kun_readings'] else 'None'
        on = ', '.join(kanji_info['on_readings'][:2]) if kanji_info['on_readings'] else 'None'
        
        breakdown += f"\n{kanji}\n"
        breakdown += f"• Meanings: {meanings}\n"
        breakdown += f"• Kun: {kun}\n"
        breakdown += "━━━━━━━━━━━━━━━━━━━━\n"
    
    return breakdown

def get_notes_in_deck(deck_name):
    """Get all note IDs in a specific deck."""
    query = f'"deck:{deck_name}"'
    note_ids = anki_request('findNotes', query=query)
    return note_ids

def get_notes_info(note_ids):
    """Get detailed information about notes."""
    return anki_request('notesInfo', notes=note_ids)

def update_note(note_id, fields):
    """Update note fields in Anki."""
    note = {
        'id': note_id,
        'fields': fields
    }
    anki_request('updateNoteFields', note=note)

def enrich_card(note_info, dry_run=False):
    """Enrich a single card with kanji breakdown."""
    note_id = note_info['noteId']
    fields = note_info.get('fields', {})
    
    front = fields.get('Front', {}).get('value', '')
    back = fields.get('Back', {}).get('value', '')
    
    # Skip if already enriched
    if '📖 Kanji Breakdown:' in back:
        return False, "Already enriched"
    
    # Extract kanji from front
    kanji_chars = extract_kanji(front)
    
    if not kanji_chars:
        return False, "No kanji found"
    
    print(f"   🔍 Processing: {front}")
    print(f"      Found {len(kanji_chars)} kanji: {', '.join(kanji_chars)}")
    
    # Get information for each kanji
    kanji_info_list = []
    for kanji in kanji_chars:
        print(f"      Fetching info for: {kanji}...", end=' ')
        info = get_kanji_info(kanji)
        if info:
            kanji_info_list.append(info)
            print("✓")
        else:
            print("✗")
    
    if not kanji_info_list:
        return False, "Could not fetch kanji info"
    
    # Build enriched back content
    kanji_breakdown = format_kanji_breakdown(kanji_info_list)
    new_back = back + kanji_breakdown
    
    if dry_run:
        print(f"   📝 [DRY RUN] Would update card:")
        print(f"      Front: {front}")
        print(f"      New back length: {len(new_back)} chars")
        return True, "Dry run success"
    
    # Update the note
    update_note(note_id, {'Back': new_back})
    return True, "Updated successfully"

def main():
    """Main function to enrich cards in specified deck."""
    print("="*80)
    print("🎴 Anki Card Enrichment Tool")
    print("="*80)
    print(f"Target deck: {TEST_DECK}")
    print()
    
    # Check connection to Anki
    print("1. Checking connection to Anki...")
    try:
        version = anki_request('version')
        print(f"   ✅ Connected to AnkiConnect (version {version})")
    except Exception as e:
        print(f"   ❌ Error: Could not connect to Anki.")
        print(f"   Make sure Anki is running with AnkiConnect add-on installed.")
        print(f"   Error details: {e}")
        return
    
    # Get notes from deck
    print(f"\n2. Fetching notes from deck '{TEST_DECK}'...")
    try:
        note_ids = get_notes_in_deck(TEST_DECK)
        print(f"   ✅ Found {len(note_ids)} notes")
    except Exception as e:
        print(f"   ❌ Error fetching notes: {e}")
        return
    
    if not note_ids:
        print(f"   ⚠️  No notes found in deck '{TEST_DECK}'")
        return
    
    # Get detailed note information
    print("\n3. Getting note details...")
    try:
        notes_info = get_notes_info(note_ids)
        print(f"   ✅ Retrieved details for {len(notes_info)} notes")
    except Exception as e:
        print(f"   ❌ Error getting note details: {e}")
        return
    
    # Ask for confirmation
    print("\n" + "="*80)
    print("⚠️  IMPORTANT: This will modify your Anki cards!")
    print("="*80)
    print(f"About to enrich {len(notes_info)} cards in deck '{TEST_DECK}'")
    print("Each card will have kanji breakdown added to the back.")
    print()
    
    choice = input("Continue? (yes/no/dry-run): ").strip().lower()
    
    if choice not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        return
    
    dry_run = choice in ['dry-run', 'dry']
    
    # Process each note
    print(f"\n4. {'[DRY RUN] ' if dry_run else ''}Enriching cards...")
    print("="*80)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, note_info in enumerate(notes_info, 1):
        print(f"\n[{i}/{len(notes_info)}]")
        try:
            success, message = enrich_card(note_info, dry_run=dry_run)
            if success:
                print(f"   ✅ {message}")
                success_count += 1
            else:
                print(f"   ⏭️  Skipped: {message}")
                skip_count += 1
        except Exception as e:
            print(f"   ❌ Error: {e}")
            error_count += 1
    
    # Summary
    print("\n" + "="*80)
    print("🎉 ENRICHMENT COMPLETE!")
    print("="*80)
    print(f"Total cards processed: {len(notes_info)}")
    print(f"  ✅ Successfully enriched: {success_count}")
    print(f"  ⏭️  Skipped: {skip_count}")
    print(f"  ❌ Errors: {error_count}")
    print("="*80)
    
    if dry_run:
        print("\n💡 This was a dry run. No cards were actually modified.")
        print("   Run again and choose 'yes' to apply changes.")

if __name__ == '__main__':
    main()





