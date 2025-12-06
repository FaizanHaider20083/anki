# Japanese Anki Tools

Scripts and data for building and maintaining Japanese (JLPT) Anki decks: vocab from Google Drive, kanji decks with similar-kanji data, and grammar imports.

## Setup

- Python 3, `pip install -r requirements.txt`
- [Anki](https://apps.ankiweb.net/) with AnkiConnect for local sync
- Google Drive API credentials (`creds.json`) for the word-queue integration

## Main scripts

- **anki.py** – Sync words from Google Drive “Anki Word Queue” folder into Anki
- **create_kanji_deck.py** – Build kanji deck from `kanji_deck_data_filled.json`
- **import_grammar.py** / **import_grammar_n3.py** – Import JLPT grammar from CSV/text into Anki
- **scrape_jlpt_vocab.py** – Scrape or load JLPT N2/N3 vocab
- **build_kanji_deck_json.py** / **build_unique_kanji.py** – Build kanji deck JSON from sources
- **populate_similar_kanji.py** / **fix_kanji_deck.py** – Similar-kanji data and deck fixes

## Data

- `niai data/data/` – Kanji/vocab and level CSVs
- `tryN3data/` – N3 grammar text sources
- `JLPTgrammar.csv` – Grammar patterns for import
