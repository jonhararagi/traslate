# NovelTrad

NovelTrad is a local-first Windows-friendly reader and translation workspace for light novels, webnovels, and fanfiction. It is designed around a calm reading experience, persistent per-book terminology, protected names, and optional help from a chat website without paid API keys.

> **Development status:** early MVP, not a finished translator. The current branch implements a local web library, SQLite persistence, EPUB/PDF text import, chapter reading, saved reading position, a separate translation editor with version snapshots, and a per-book glossary editor. It does not yet automatically translate text, implement OCR, or export translated books.

## Product principles

- EPUB and PDF are the only book-import formats.
- The app binds to `127.0.0.1` by default and stores its library on the local computer.
- No paid API is required by the current foundation.
- Translation must be a pluggable subsystem: deterministic dictionaries/rules and translation memory can work offline; an optional local neural model can improve naturalness without a remote API. These are distinct modes and must never be mislabeled.
- Chat-web assistance should prepare a contextual prompt for the user to review and send manually. It must not silently send private book text to a third party.
- Originals remain immutable; translations and corrections are versioned separately.
- Reading must be the default experience. Advanced editing and glossary management stay out of the way until requested.

## Requirements

- Python 3.11 or newer.
- Internet is only needed to install dependencies initially. EPUB/PDF import and local storage run on the computer.
- A translation engine is **not yet configured**. Offline translation of arbitrary new sentences is not provided by this foundation.

## Run on Windows

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
noveltrad
```

Then open <http://127.0.0.1:8765>. The application intentionally binds to loopback, not to the public network.

To run without installing the command entry point:

```powershell
python -m noveltrad.main
```

On other platforms, create a virtual environment, install `.[test]`, and run `noveltrad`.

## Local data

- Windows: `%LOCALAPPDATA%\NovelTrad`
- Linux/macOS: `$XDG_DATA_HOME/noveltrad`, or `~/.local/share/noveltrad`
- Tests and development can override this using `NOVELTRAD_HOME`.

Imported source files are stored under `imports/`; SQLite stores books, extracted sections, glossary entries, and corrections. Backups and user-facing restore controls are planned, not yet implemented.

## Current API

- `GET /api/health` — local service status.
- `GET /api/books` — imported library.
- `POST /api/books/import` — import an EPUB or text-based PDF (100 MB limit).
- `GET /api/books/{book_id}/chapters` — extracted sections.
- `GET /api/books/{book_id}/glossary` — per-book and global glossary entries.
- `POST /api/books/{book_id}/glossary` — add a glossary rule (`preserve`, `translate`, `contextual`, or `protect`).
- `PUT /api/books/{book_id}/progress` — persist the current chapter and reading scroll position.
- `PUT /api/chapters/{chapter_id}/translation` — save a chapter translation separately from immutable imported text.
- `GET /api/chapters/{chapter_id}/translation/versions` — inspect saved prior translation snapshots.
- `POST /api/chapters/{chapter_id}/translation/restore/{version_number}` — restore a snapshot while preserving the replaced text in history.
- `GET /api/docs` — local API documentation.

Scanned PDFs currently return a clear error because OCR has not been integrated. EPUB import extracts document sections in EPUB reading order where provided by the library; complex books may require later refinement of navigation and metadata handling.

## Development checks

```powershell
pytest
```

## Roadmap

1. Harden import and persistence with tests, file validation, backups, and recovery.
2. Finish reader UX: broader accessibility checks, automated regression coverage, and more theme/typography settings.
3. Add translation-history restore, stronger glossary validation, entity management, and translation-memory workflows.
4. Evaluate offline English→Spanish and Japanese→Spanish engines separately; keep rule-based mode distinct from local neural translation.
5. Add contextual prompt generation for user-mediated chat-web assistance.
6. Add versioned translation, quality checks, and TXT/EPUB/PDF export.
7. Package and test the Windows application on a clean machine.
