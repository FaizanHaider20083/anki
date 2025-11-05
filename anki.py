#!/usr/bin/env python3
"""
Script to fetch Japanese vocabulary from Google Drive and add to Anki deck.
Reads files from 'Anki Word Queue' folder and adds cards to the specified deck.
Always adds words for spaced repetition benefits, but includes deck references
for words that already exist in other decks.
"""

import os
import re
import json
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import requests

# Google Drive API settings
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FOLDER_NAME = 'Anki Word Queue'

# AnkiConnect settings
ANKI_CONNECT_URL = 'http://localhost:8765'
DECK_NAME = 'n3_tn'  # Change this to your desired deck name for new words
# The script will check for duplicates across ALL existing decks before adding to this deck

# Logging settings
FAILED_WORDS_FILE = 'failed_words.txt'

def get_google_drive_service():
    """Authenticate and return Google Drive service."""
    creds = None
    
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('creds.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('drive', 'v3', credentials=creds)

def find_folder_id(service, folder_name):
    """Find the folder ID by folder name."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    
    if not items:
        raise Exception(f"Folder '{folder_name}' not found in Google Drive")
    
    return items[0]['id']

def get_files_from_folder(service, folder_id):
    """Get all files from the specified folder."""
    query = f"'{folder_id}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        spaces='drive',
        fields='files(id, name, mimeType)',
        pageSize=100
    ).execute()
    
    return results.get('files', [])

def download_file_content(service, file_id, mime_type):
    """Download and return file content as text."""
    try:
        # For Google Docs, export as plain text
        if mime_type == 'application/vnd.google-apps.document':
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        else:
            # For regular files
            request = service.files().get_media(fileId=file_id)
        
        file_handle = io.BytesIO()
        downloader = MediaIoBaseDownload(file_handle, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        file_handle.seek(0)
        content = file_handle.read().decode('utf-8')
        return content
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

def parse_vocabulary_entries(content, filename=""):
    """Parse vocabulary entries from file content.
    
    Supports multiple formats:
    1. ぼく (boku): I (used by males)
    2. 会社　(かいしゃ - kaisha) - company
    3. 食べる (taberu) - to eat
    4. いつも (itsumo): always
    """
    entries = []
    failed_parses = []
    
    # Pattern 1: word (reading): meaning
    pattern1 = r'^(.+?)\s*\(([^)]+)\)\s*:\s*(.+)$'
    
    # Pattern 2: word (kana - romaji) - meaning
    # Example: 会社　(かいしゃ - kaisha) - company
    pattern2 = r'^(.+?)\s*\(([^\-)]+?)\s*-\s*([^)]+)\)\s*-\s*(.+)$'
    
    # Pattern 3: word (reading) - meaning
    # Example: 食べる (taberu) - to eat
    pattern3 = r'^(.+?)\s*\(([^)]+)\)\s*-\s*(.+)$'
    
    lines = content.strip().split('\n')
    line_number = 0
    
    for line in lines:
        line_number += 1
        original_line = line
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip comment lines
        if line.startswith('#'):
            continue
        
        parsed = False
        
        # Try Pattern 1: word (reading): meaning
        match = re.match(pattern1, line)
        if match:
            kanji = match.group(1).strip()
            reading = match.group(2).strip()
            meaning = match.group(3).strip()
            
            entries.append({
                'kanji': kanji,
                'reading': reading,
                'meaning': meaning,
                'original_line': original_line,
                'source_file': filename,
                'line_number': line_number
            })
            parsed = True
        
        # Try Pattern 2: word (kana - romaji) - meaning
        if not parsed:
            match = re.match(pattern2, line)
            if match:
                kanji = match.group(1).strip()
                kana = match.group(2).strip()
                romaji = match.group(3).strip()
                meaning = match.group(4).strip()
                
                # Combine kana and romaji for reading
                reading = f"{kana} - {romaji}"
                
                entries.append({
                    'kanji': kanji,
                    'reading': reading,
                    'meaning': meaning,
                    'original_line': original_line,
                    'source_file': filename,
                    'line_number': line_number
                })
                parsed = True
        
        # Try Pattern 3: word (reading) - meaning
        if not parsed:
            match = re.match(pattern3, line)
            if match:
                kanji = match.group(1).strip()
                reading = match.group(2).strip()
                meaning = match.group(3).strip()
                
                entries.append({
                    'kanji': kanji,
                    'reading': reading,
                    'meaning': meaning,
                    'original_line': original_line,
                    'source_file': filename,
                    'line_number': line_number
                })
                parsed = True
        
        # If none of the patterns matched, log detailed failure
        if not parsed:
            error_details = {
                'line': original_line,
                'file': filename,
                'line_number': line_number,
                'reason': 'No pattern matched'
            }
            failed_parses.append(error_details)
            
            print(f"⚠️  PARSE ERROR [Line {line_number}]:")
            print(f"    File: {filename}")
            print(f"    Line: {original_line}")
            print(f"    Reason: Line doesn't match any supported format")
            print(f"    Expected formats:")
            print(f"      - word (reading): meaning")
            print(f"      - word (kana - romaji) - meaning")
            print(f"      - word (reading) - meaning")
            print()
    
    return entries, failed_parses

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
        print(f"Creating deck: {deck_name}")
        anki_request('createDeck', deck=deck_name)
    else:
        print(f"Deck '{deck_name}' already exists")

def get_all_decks():
    """Get all existing Anki decks."""
    return anki_request('deckNames')

def card_exists_in_any_deck(kanji):
    """Check if a card with the given kanji already exists in any deck."""
    # Search for cards with the kanji in the front field across all decks
    query = f'"front:{kanji}"'
    note_ids = anki_request('findNotes', query=query)
    return len(note_ids) > 0

def find_deck_containing_word(kanji):
    """Find which deck(s) contain the given kanji word."""
    # Search for cards with the kanji in the front field across all decks
    query = f'"front:{kanji}"'
    note_ids = anki_request('findNotes', query=query)
    
    if not note_ids:
        return []
    
    # Get note info to find card IDs, then get card info to find deck names
    notes_info = anki_request('notesInfo', notes=note_ids)
    deck_names = []
    
    for note_info in notes_info:
        card_ids = note_info.get('cards', [])
        if card_ids:
            # Get card info to find deck names
            cards_info = anki_request('cardsInfo', cards=card_ids)
            for card_info in cards_info:
                deck_name = card_info.get('deckName', '')
                if deck_name and deck_name not in deck_names:
                    deck_names.append(deck_name)
    
    return deck_names

def card_exists(deck_name, kanji):
    """Check if a card with the given kanji already exists in the specific deck."""
    # Search for cards with the kanji in the front field
    query = f'"deck:{deck_name}" "front:{kanji}"'
    note_ids = anki_request('findNotes', query=query)
    return len(note_ids) > 0

def note_exists_with_content(deck_name, entry, existing_decks=None):
    """Check if a note with the exact same content already exists in the target deck."""
    # Build the expected back content
    back_content = f"({entry['reading']})\n\n{entry['meaning']}"
    if existing_decks:
        deck_info = ", ".join(existing_decks)
        back_content = f"📚 Previously in: {deck_info}\n\n{back_content}"
    
    # Search for notes with the same front and back content in the target deck
    kanji = entry['kanji']
    query = f'"deck:{deck_name}" "front:{kanji}"'
    note_ids = anki_request('findNotes', query=query)
    
    if not note_ids:
        return False
    
    # Get the actual note content to compare
    notes_info = anki_request('notesInfo', notes=note_ids)
    for note_info in notes_info:
        fields = note_info.get('fields', {})
        front_field = fields.get('Front', {}).get('value', '')
        back_field = fields.get('Back', {}).get('value', '')
        
        # Check if both front and back match exactly
        if front_field == entry['kanji'] and back_field == back_content:
            return True
    
    return False

def add_card_to_anki(deck_name, entry, existing_decks=None):
    """Add a new card to Anki deck.
    
    Card format:
    - Front: Only the kanji/kana
    - Back: Reading + meaning (with deck info if word exists elsewhere)
    """
    # Build the back content
    back_content = f"({entry['reading']})\n\n{entry['meaning']}"
    
    # Add deck information if the word exists in other decks
    if existing_decks:
        deck_info = ", ".join(existing_decks)
        back_content = f"📚 Previously in: {deck_info}\n\n{back_content}"
    
    note = {
        'deckName': deck_name,
        'modelName': 'Basic',
        'fields': {
            'Front': entry['kanji'],
            'Back': back_content
        },
        'tags': ['japanese', 'vocabulary', 'auto-imported'],
        'options': {
            'allowDuplicate': False,
            'duplicateScope': 'deck',  # Only check for duplicates within the same deck
            'duplicateScopeOptions': {
                'deckName': deck_name,
                'checkChildren': False
            }
        }
    }
    
    try:
        anki_request('addNote', note=note)
        return True, None
    except Exception as e:
        error_msg = str(e)
        return False, error_msg

def write_failed_words(failed_words):
    """Write failed words to a file for retry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(FAILED_WORDS_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'='*80}\n")
        f.write(f"Sync Run: {timestamp}\n")
        f.write(f"{'='*80}\n\n")
        
        for failure in failed_words:
            f.write(f"Original Line: {failure['original_line']}\n")
            f.write(f"Source File: {failure['source_file']}\n")
            f.write(f"Line Number: {failure['line_number']}\n")
            f.write(f"Error Type: {failure['error_type']}\n")
            f.write(f"Error Details: {failure['error_details']}\n")
            
            if 'parsed_data' in failure:
                f.write(f"Parsed Data:\n")
                f.write(f"  - Kanji: {failure['parsed_data'].get('kanji', 'N/A')}\n")
                f.write(f"  - Reading: {failure['parsed_data'].get('reading', 'N/A')}\n")
                f.write(f"  - Meaning: {failure['parsed_data'].get('meaning', 'N/A')}\n")
            
            f.write("-" * 80 + "\n\n")

def main():
    """Main function to sync Google Drive vocabulary to Anki."""
    print("Starting Anki Drive Sync...")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Track all failures
    all_failed_words = []
    
    # Connect to Google Drive
    print("\n1. Connecting to Google Drive...")
    try:
        service = get_google_drive_service()
        print("   ✅ Connected successfully")
    except Exception as e:
        print(f"   ❌ Error connecting to Google Drive: {e}")
        return
    
    # Find the folder
    print(f"\n2. Finding folder '{FOLDER_NAME}'...")
    try:
        folder_id = find_folder_id(service, FOLDER_NAME)
        print(f"   ✅ Found folder ID: {folder_id}")
    except Exception as e:
        print(f"   ❌ Error finding folder: {e}")
        return
    
    # Get files from folder
    print("\n3. Fetching files from folder...")
    try:
        files = get_files_from_folder(service, folder_id)
        print(f"   ✅ Found {len(files)} file(s)")
    except Exception as e:
        print(f"   ❌ Error fetching files: {e}")
        return
    
    # Get all existing decks and ensure target deck exists
    print(f"\n4. Checking Anki decks...")
    try:
        all_decks = get_all_decks()
        print(f"   ✅ Found {len(all_decks)} existing deck(s): {', '.join(all_decks)}")
        
        # Ensure target deck exists
        ensure_deck_exists(DECK_NAME)
        print(f"   ✅ Target deck '{DECK_NAME}' ready")
    except Exception as e:
        print(f"   ❌ Error: Could not connect to Anki.")
        print(f"   Make sure Anki is running with AnkiConnect add-on installed.")
        print(f"   Error details: {e}")
        return
    
    # Process each file
    print("\n5. Processing vocabulary files...")
    total_entries = 0
    added_count = 0
    skipped_count = 0  # Words that already exist in target deck
    duplicate_count = 0  # Words that existed in other decks
    parse_error_count = 0
    anki_error_count = 0
    
    for file in files:
        print(f"\n{'='*70}")
        print(f"   📄 Processing: {file['name']}")
        print(f"{'='*70}")
        
        content = download_file_content(service, file['id'], file['mimeType'])
        
        if not content:
            print(f"   ⚠️  Skipping file (could not download)")
            continue
        
        # Parse entries with detailed error tracking
        entries, failed_parses = parse_vocabulary_entries(content, file['name'])
        
        print(f"\n   📊 Parse Results:")
        print(f"      - Successfully parsed: {len(entries)} entries")
        print(f"      - Failed to parse: {len(failed_parses)} lines")
        
        # Track parse failures
        for failed_parse in failed_parses:
            parse_error_count += 1
            all_failed_words.append({
                'original_line': failed_parse['line'],
                'source_file': failed_parse['file'],
                'line_number': failed_parse['line_number'],
                'error_type': 'PARSE_ERROR',
                'error_details': failed_parse['reason']
            })
        
        # Process successfully parsed entries
        print(f"\n   🔄 Adding cards to Anki...")
        for entry in entries:
            total_entries += 1
            
            # First, check if word already exists in the target deck
            try:
                if card_exists(DECK_NAME, entry['kanji']):
                    print(f"   ⏭️  [Line {entry['line_number']}] Skipping (already exists in target deck): {entry['kanji']}")
                    print(f"      This word already exists in {DECK_NAME}")
                    skipped_count += 1
                    continue
            except Exception as e:
                print(f"   ⚠️  [Line {entry['line_number']}] Error checking target deck: {entry['kanji']}")
                print(f"      Error: {e}")
                # Continue anyway, let AnkiConnect handle the duplicate check
            
            # Check if card exists in OTHER decks (not the target deck) and get deck info
            existing_decks = []
            try:
                if card_exists_in_any_deck(entry['kanji']):
                    all_decks = find_deck_containing_word(entry['kanji'])
                    # Filter out the target deck from the list
                    existing_decks = [deck for deck in all_decks if deck != DECK_NAME]
                    if existing_decks:
                        print(f"   🔄 [Line {entry['line_number']}] Word exists in other decks: {', '.join(existing_decks)}")
                        print(f"      Will add to {DECK_NAME} with deck reference for spaced repetition")
            except Exception as e:
                print(f"   ⚠️  [Line {entry['line_number']}] Error checking other decks: {entry['kanji']}")
                print(f"      Error: {e}")
                # Don't fail here, just continue without deck references
            
            # Add new card (only if not in target deck)
            print(f"   🔍 [Line {entry['line_number']}] Attempting to add: {entry['kanji']}")
            print(f"      Target deck: {DECK_NAME}")
            print(f"      Existing decks: {', '.join(existing_decks) if existing_decks else 'None'}")
            
            success, error_msg = add_card_to_anki(DECK_NAME, entry, existing_decks)
            
            if success:
                deck_ref = f" (ref: {', '.join(existing_decks)})" if existing_decks else ""
                print(f"   ✅ [Line {entry['line_number']}] Added: {entry['kanji']} → ({entry['reading']}) → {entry['meaning'][:50]}...{deck_ref}")
                added_count += 1
                if existing_decks:
                    duplicate_count += 1
            else:
                print(f"   ❌ [Line {entry['line_number']}] FAILED to add card:")
                print(f"      Word: {entry['kanji']}")
                print(f"      Reading: {entry['reading']}")
                print(f"      Meaning: {entry['meaning']}")
                print(f"      Target deck: {DECK_NAME}")
                print(f"      Existing decks: {', '.join(existing_decks) if existing_decks else 'None'}")
                print(f"      Error: {error_msg}")
                print(f"      Full error details:")
                print(f"        - This usually means the exact same note already exists in the target deck")
                print(f"        - Check if the word with the same reading and meaning already exists")
                print()
                
                anki_error_count += 1
                all_failed_words.append({
                    'original_line': entry['original_line'],
                    'source_file': entry['source_file'],
                    'line_number': entry['line_number'],
                    'error_type': 'ADD_CARD_ERROR',
                    'error_details': error_msg,
                    'parsed_data': entry
                })
    
    # Write failed words to file if any
    if all_failed_words:
        print(f"\n📝 Writing failed words to {FAILED_WORDS_FILE}...")
        write_failed_words(all_failed_words)
        print(f"   ✅ Failed words logged to file")
    
    # Summary
    print("\n" + "="*80)
    print("🎉 SYNC COMPLETE!")
    print("="*80)
    print(f"Total entries found: {total_entries + parse_error_count}")
    print(f"  ✅ Successfully added to Anki: {added_count}")
    print(f"  ⏭️  Skipped (already in target deck): {skipped_count}")
    print(f"  🔄 Added with deck references (for spaced repetition): {duplicate_count}")
    print(f"  ⚠️  Parse errors: {parse_error_count}")
    print(f"  ❌ Anki errors: {anki_error_count}")
    print(f"\nTotal failures: {len(all_failed_words)}")
    if all_failed_words:
        print(f"  → See {FAILED_WORDS_FILE} for details on failed words")
    print("="*80)

if __name__ == '__main__':
    main()