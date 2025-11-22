#!/usr/bin/env python3
"""
Populate a Similar field on Anki cards with top-5 similar kanji per character,
using the prebuilt similarity data (kanjis_min.json).

Steps:
1) Load similarity data from kanjis_min.json (Character -> Similar list with scores).
2) For each deck in DECK_NAMES:
   - fetch notes via AnkiConnect
   - extract kanji characters from the Front field (configurable)
   - look up top 5 similars per kanji (if available)
   - populate/update the SIMILAR_FIELD with a string like:
       試験 → 試:験:経:...
       (actually flattened list of unique similars, highest scores first)
3) Supports dry-run.

Configuration:
  - DECK_NAMES: list of deck names to process
  - FRONT_FIELD: which field to read kanji from (default "Front")
  - SIMILAR_FIELD: which field to write (e.g., "Similar" or "Notes")
  - MAX_PER_KANJI: 5
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
SIMILAR_FIELD = "Similar"
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
    # simple space-separated list
    return " ".join(similars)


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

        new_val = format_similar_field(collected)
        current_val = fields.get(SIMILAR_FIELD, {}).get("value", "")
        if current_val == new_val:
            skipped += 1
            continue

        print(f"Note {n['noteId']}: {front_val} -> {new_val}")
        if not DRY_RUN:
            anki_request(
                "updateNoteFields",
                note={"id": n["noteId"], "fields": {SIMILAR_FIELD: new_val}},
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

