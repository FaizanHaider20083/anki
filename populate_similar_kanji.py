#!/usr/bin/env python3
"""
Append a Similar Kanji section to the Back field for each card, using
prebuilt similarity data (kanjis_min.json).

Behavior:
- Extract kanji from FRONT_FIELD, look up top MAX_PER_KANJI similars per kanji,
  dedup across the card, and append a block to Back:

  ━━ Similar Kanji ━━
  試 証 経 ...

- Idempotent: removes any existing Similar Kanji block before re-adding.
- Dry-run support.

Configuration:
  - DECK_NAMES: decks to process
  - FRONT_FIELD: source field for kanji
  - BACK_FIELD: field to append into (Back)
  - MAX_PER_KANJI: top-N per kanji
  - DRY_RUN: True/False
"""

import json
import re
import requests
from pathlib import Path
from typing import Dict, List, Set

ANKI_CONNECT_URL = "http://localhost:8765"
SIM_DATA_PATH = Path("kanjis_min.json")

# --- Config ---
DECK_NAMES = ["n3_tn_ch9"]  # change to your deck(s)
FRONT_FIELD = "Front"
BACK_FIELD = "Back"
MAX_PER_KANJI = 5
DRY_RUN = True  # set False to update Anki
# ---------------

KANJI_REGEX = re.compile(
    r"["
    r"\u4E00-\u9FFF"          # CJK Unified Ideographs
    r"\u3400-\u4DBF"          # CJK Extension A
    r"\U00020000-\U0002A6DF"  # CJK Extension B
    r"]"
)


# --------------- Helpers -----------------
def anki_request(action: str, **params):
    payload = {"action": action, "version": 6, "params": params}
    r = requests.post(ANKI_CONNECT_URL, json=payload)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data.get("result")


def load_similarity() -> Dict[str, List[Dict]]:
    if not SIM_DATA_PATH.exists():
        raise FileNotFoundError(f"Missing similarity data: {SIM_DATA_PATH}")
    data = json.loads(SIM_DATA_PATH.read_text(encoding="utf-8"))
    # Build map for quick lookup
    return {e["Character"]: e.get("Similar", []) for e in data if e.get("Character")}


def extract_kanji(text: str) -> List[str]:
    return KANJI_REGEX.findall(text or "")


def top_similars(sim_map: Dict[str, List[Dict]], kanji: str, k: int) -> List[str]:
    sims = sim_map.get(kanji, [])
    sims_sorted = sorted(sims, key=lambda x: x.get("Score", 0), reverse=True)
    return [s["Kanji"] for s in sims_sorted[:k]]


def format_similar_field(similars: List[str]) -> str:
    return " ".join(similars)


SIM_BLOCK_HEADER = "━━ Similar Kanji ━━"


def strip_existing_block(back_text: str) -> str:
    """
    Remove existing Similar Kanji block, if any.
    Looks for header line and removes until the next blank line or end of text.
    """
    pattern = re.compile(rf"\n?{re.escape(SIM_BLOCK_HEADER)}\n.*?(?:\n\s*\n|$)", re.DOTALL)
    return re.sub(pattern, "", back_text).rstrip()


def process_deck(deck: str, sim_map: Dict[str, List[Dict]]):
    print(f"\n--- Deck: {deck} ---")
    note_ids = anki_request("findNotes", query=f'deck:"{deck}"')
    print(f"Found {len(note_ids)} notes")
    if not note_ids:
        return

    notes = anki_request("notesInfo", notes=note_ids)

    updated = 0
    skipped = 0

    for n in notes:
        fields = n.get("fields", {})
        front_val = fields.get(FRONT_FIELD, {}).get("value", "")
        back_val = fields.get(BACK_FIELD, {}).get("value", "")

        kanji_chars = extract_kanji(front_val)
        if not kanji_chars:
            skipped += 1
            continue

        collected: List[str] = []
        seen: Set[str] = set()
        for ch in kanji_chars:
            for s in top_similars(sim_map, ch, MAX_PER_KANJI):
                if s not in seen:
                    seen.add(s)
                    collected.append(s)

        if not collected:
            skipped += 1
            continue

        sim_text = format_similar_field(collected)

        new_back = strip_existing_block(back_val)
        if new_back:
            new_back += "\n\n"
        new_back += f"{SIM_BLOCK_HEADER}\n{sim_text}"

        if new_back == back_val:
            skipped += 1
            continue

        print(f"Note {n['noteId']}:")
        print(f"  Front: {front_val}")
        print(f"  Back (new tail):\n    {SIM_BLOCK_HEADER}\n    {sim_text}")

        if not DRY_RUN:
            anki_request(
                "updateNoteFields",
                note={"id": n["noteId"], "fields": {BACK_FIELD: new_back}},
            )
        updated += 1

    print(f"Updated: {updated}, Skipped: {skipped}")


def main():
    sim_map = load_similarity()
    try:
        version = anki_request("version")
        print(f"Connected to AnkiConnect (version {version})")
    except Exception as e:
        print(f"Could not connect to Anki: {e}")
        return

    for deck in DECK_NAMES:
        process_deck(deck, sim_map)

    if DRY_RUN:
        print("\nDRY RUN ONLY. Set DRY_RUN = False to apply changes.")


if __name__ == "__main__":
    main()

