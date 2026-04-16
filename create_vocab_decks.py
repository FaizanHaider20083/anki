#!/usr/bin/env python3
"""
Phase 3: Push JLPT vocab from JSON files to Anki via AnkiConnect.

Reads N2_vocab.json, N3_vocab.json, N4_vocab.json, N5_vocab.json
and creates one Anki deck per file.

Card format:
- Front: Kanji (or hiragana if no kanji)
- Back: Hiragana reading + English meaning

Requires Anki running with AnkiConnect add-on installed.
"""

import json
import re
import sys
from pathlib import Path

import requests

ANKI_CONNECT_URL = "http://localhost:8765"
WORD_LISTS_DIR = Path(__file__).resolve().parent / "wordLists"

JSON_TO_DECK = {
    "N5_vocab.json": "JLPT_N5_Vocab",
    "N4_vocab.json": "JLPT_N4_Vocab",
    "N3_vocab.json": "JLPT_N3_Vocab",
    "N2_vocab.json": "JLPT_N2_Vocab",
}

DRY_RUN = False
BATCH_SIZE = 50


def anki_request(action: str, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params})
    response = requests.post(ANKI_CONNECT_URL, data=payload)
    data = response.json()
    if data.get("error"):
        raise Exception(f"AnkiConnect error: {data['error']}")
    return data.get("result")


def ensure_deck_exists(deck_name: str):
    existing = anki_request("deckNames")
    if deck_name not in existing:
        anki_request("createDeck", deck=deck_name)
        print(f"    Created deck: {deck_name}")
    else:
        print(f"    Deck already exists: {deck_name}")


def format_front(entry: dict) -> str:
    word = entry["kanji"] or entry["hiragana"]
    return f"<div style='font-size: 3em; text-align: center;'>{word}</div>"


def format_back(entry: dict) -> str:
    parts = []

    if entry["kanji"] and entry["hiragana"]:
        parts.append(
            f"<div style='font-size: 1.6em; text-align: center; color: #27ae60; "
            f"margin-bottom: 12px;'>{entry['hiragana']}</div>"
        )

    if entry.get("english"):
        parts.append(
            f"<div style='font-size: 1.2em; text-align: center; color: #2c3e50;'>"
            f"{entry['english']}</div>"
        )

    return "\n".join(parts)


def build_note(deck_name: str, entry: dict, level_tag: str) -> dict:
    return {
        "deckName": deck_name,
        "modelName": "Basic",
        "fields": {
            "Front": format_front(entry),
            "Back": format_back(entry),
        },
        "tags": ["jlpt", level_tag, "vocabulary", "auto-imported"],
        "options": {
            "allowDuplicate": False,
            "duplicateScope": "deck",
            "duplicateScopeOptions": {
                "deckName": deck_name,
                "checkChildren": False,
            },
        },
    }


def add_notes_batch(notes: list) -> tuple:
    """Add notes in batch. Returns (success_count, duplicate_count, error_count, errors)."""
    if DRY_RUN:
        return len(notes), 0, 0, []

    result = anki_request("addNotes", notes=notes)

    success = 0
    duplicates = 0
    errors = []
    for i, note_id in enumerate(result):
        if note_id is not None:
            success += 1
        else:
            duplicates += 1

    return success, duplicates, len(errors), errors


def process_deck(json_name: str, deck_name: str):
    json_path = WORD_LISTS_DIR / json_name

    if not json_path.exists():
        print(f"    SKIP: {json_path} not found")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        entries = json.load(f)

    level_match = re.search(r"N(\d)", json_name)
    level_tag = f"n{level_match.group(1)}" if level_match else "unknown"

    print(f"\n  {json_name} -> deck '{deck_name}'")
    print(f"    Entries: {len(entries)}")

    if not DRY_RUN:
        ensure_deck_exists(deck_name)

    # Preview first card
    if entries:
        sample = entries[0]
        front_word = sample["kanji"] or sample["hiragana"]
        print(f"    Preview: Front=[{front_word}]  Back=[{sample.get('hiragana', '')} / {sample.get('english', '')[:40]}]")

    total_success = 0
    total_dupes = 0
    total_errors = 0

    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i : i + BATCH_SIZE]
        notes = [build_note(deck_name, entry, level_tag) for entry in batch]

        success, dupes, errs, error_details = add_notes_batch(notes)
        total_success += success
        total_dupes += dupes
        total_errors += errs

        progress = min(i + BATCH_SIZE, len(entries))
        print(f"    Progress: {progress}/{len(entries)}  (added: {total_success}, dupes: {total_dupes}, errors: {total_errors})")

    print(f"    DONE: {total_success} added, {total_dupes} duplicates skipped, {total_errors} errors")
    return total_success, total_dupes, total_errors


def main():
    print("Phase 3: Pushing vocab to Anki")
    if DRY_RUN:
        print("  [DRY RUN MODE - no changes will be made]\n")

    # Check AnkiConnect
    print("  Connecting to AnkiConnect...")
    try:
        version = anki_request("version")
        print(f"    Connected (AnkiConnect v{version})")
    except Exception as e:
        print(f"    FAILED: {e}")
        print("    Make sure Anki is running with AnkiConnect add-on installed.")
        sys.exit(1)

    grand_success = 0
    grand_dupes = 0
    grand_errors = 0

    for json_name, deck_name in JSON_TO_DECK.items():
        result = process_deck(json_name, deck_name)
        if result:
            grand_success += result[0]
            grand_dupes += result[1]
            grand_errors += result[2]

    print(f"\n{'='*60}")
    print(f"  ALL DONE")
    print(f"  Added: {grand_success}")
    print(f"  Duplicates skipped: {grand_dupes}")
    print(f"  Errors: {grand_errors}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
