#!/usr/bin/env python3
"""
Script to clean up kanji breakdown format in enriched cards.
Removes "Grade: X | Strokes: Y" lines from old format.
"""

import json
import requests
import re

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'

# Specify which deck to clean up
TARGET_DECK = 'n3_tn_ch9'  # Change this to your first deck name

def anki_request(action, **params):
    """Send request to AnkiConnect."""
    request_json = json.dumps({'action': action, 'version': 6, 'params': params})
    response = requests.post(ANKI_CONNECT_URL, data=request_json)
    response_data = response.json()
    
    if response_data.get('error'):
        raise Exception(f"AnkiConnect error: {response_data['error']}")
    
    return response_data.get('result')

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

def clean_kanji_breakdown(back_content):
    """Remove Grade and Strokes lines from kanji breakdown."""
    # Pattern to match lines like: "• Grade: 2 | Strokes: 4"
    pattern = r'• Grade: .+? \| Strokes: .+?\n'
    
    # Remove all matching lines
    cleaned = re.sub(pattern, '', back_content)
    
    return cleaned

def cleanup_card(note_info, dry_run=False):
    """Clean up a single card's format."""
    note_id = note_info['noteId']
    fields = note_info.get('fields', {})
    
    front = fields.get('Front', {}).get('value', '')
    back = fields.get('Back', {}).get('value', '')
    
    # Check if card has kanji breakdown
    if '📖 Kanji Breakdown:' not in back:
        return False, "No kanji breakdown found"
    
    # Check if it has the old format (Grade/Strokes)
    if '• Grade:' not in back and '| Strokes:' not in back:
        return False, "Already clean format"
    
    # Clean the content
    cleaned_back = clean_kanji_breakdown(back)
    
    # Check if anything changed
    if cleaned_back == back:
        return False, "No changes needed"
    
    print(f"   🧹 Cleaning: {front}")
    
    if dry_run:
        print(f"      [DRY RUN] Would remove Grade/Strokes lines")
        # Show a sample of what would be removed
        old_lines = back.count('• Grade:')
        print(f"      Found {old_lines} Grade/Strokes line(s) to remove")
        return True, "Dry run success"
    
    # Update the note
    update_note(note_id, {'Back': cleaned_back})
    return True, "Cleaned successfully"

def main():
    """Main function to clean up cards in specified deck."""
    print("="*80)
    print("🧹 Anki Card Format Cleanup Tool")
    print("="*80)
    print(f"Target deck: {TARGET_DECK}")
    print("This will remove 'Grade: X | Strokes: Y' lines from kanji breakdowns")
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
    print(f"\n2. Fetching notes from deck '{TARGET_DECK}'...")
    try:
        note_ids = get_notes_in_deck(TARGET_DECK)
        print(f"   ✅ Found {len(note_ids)} notes")
    except Exception as e:
        print(f"   ❌ Error fetching notes: {e}")
        return
    
    if not note_ids:
        print(f"   ⚠️  No notes found in deck '{TARGET_DECK}'")
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
    print(f"About to clean up {len(notes_info)} cards in deck '{TARGET_DECK}'")
    print("Will remove 'Grade: X | Strokes: Y' lines from kanji breakdowns.")
    print()
    
    choice = input("Continue? (yes/no/dry-run): ").strip().lower()
    
    if choice not in ['yes', 'y', 'dry-run', 'dry']:
        print("Cancelled.")
        return
    
    dry_run = choice in ['dry-run', 'dry']
    
    # Process each note
    print(f"\n4. {'[DRY RUN] ' if dry_run else ''}Cleaning up cards...")
    print("="*80)
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, note_info in enumerate(notes_info, 1):
        print(f"\n[{i}/{len(notes_info)}]")
        try:
            success, message = cleanup_card(note_info, dry_run=dry_run)
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
    print("🎉 CLEANUP COMPLETE!")
    print("="*80)
    print(f"Total cards processed: {len(notes_info)}")
    print(f"  ✅ Successfully cleaned: {success_count}")
    print(f"  ⏭️  Skipped: {skip_count}")
    print(f"  ❌ Errors: {error_count}")
    print("="*80)
    
    if dry_run:
        print("\n💡 This was a dry run. No cards were actually modified.")
        print("   Run again and choose 'yes' to apply changes.")

if __name__ == '__main__':
    main()




