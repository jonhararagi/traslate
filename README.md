# NovelTrad

NovelTrad is a local-first Windows-friendly reader and translation workspace for light novels, webnovels, and fanfiction. It is designed around a calm reading experience, persistent per-book terminology, protected names, and optional help from a chat website without paid API keys.

> **Development status:** early MVP, not a finished translator. The current branch implements a local web library, SQLite persistence, EPUB/PDF text import, chapter reading, saved reading position, a separate translation editor with version snapshots, and a per-book glossary editor with CRUD controls. Fully translated books can now be exported as Spanish EPUB; automatic translation and OCR are not yet implemented.

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

Imported source files are stored under `imports/`; SQLite stores books, extracted sections, glossary entries, and corrections. The library includes user-facing backup creation, listing, and restore controls. Database snapshots use SQLite's online backup API and each snapshot includes a companion copy of the imported EPUB/PDF source files. Automatic backups run while NovelTrad is open, defaulting to every 24 hours with the newest 14 snapshots retained. On Windows, an optional Task Scheduler task can invoke a headless CLI every hour while the app is closed; the CLI checks the same persisted schedule and retention policy, validates the existing database, and refuses to create a new empty database. Frequency (1–720 hours), retention (1–100 snapshots), and enable/disable controls are available in the library UI. The schedule is stored separately from the novel database, so restoring an older library snapshot does not roll back backup preferences. Snapshots include both the SQLite database and the imported EPUB/PDF originals. Before a restore, NovelTrad validates database integrity/schema and automatically creates a safety snapshot of the current database and imported files. Retention removes the database snapshot and its matching source-file bundle together.

## Current API

- `GET /api/health` — local service status.
- `GET /api/books` — imported library.
- `POST /api/backups` — create a consistent SQLite snapshot and apply the configured retention limit.
- `python -m noveltrad.backup_cli` — headless scheduled-backup check; validates an existing library and exits without launching the web server.
- `GET /api/backups/settings` — inspect automatic-backup settings and the last successful run/error.
- `PUT /api/backups/settings` — configure automatic backups, frequency (1–720 hours), and retention (1–100 snapshots).
- `POST /api/backups/prune` — immediately remove snapshots beyond the configured retention limit.
- `GET /api/backups` — list local snapshots without exposing absolute filesystem paths.
- `POST /api/backups/{backup_name}/restore` — validate and restore a named snapshot after automatically preserving the current database as a safety copy.
- `POST /api/books/import` — import an EPUB or text-based PDF (100 MB limit). PDF imports must have a PDF signature; EPUB imports must be valid ZIP packages with the required EPUB structure, no encrypted entries, at most 5,000 archive entries, no more than 500 MB uncompressed content, and a maximum 200:1 compression ratio.
- `GET /api/books/{book_id}/export/epub` — export the saved Spanish translations as EPUB; export is blocked until every section has a translation.
- `GET /api/books/{book_id}/chapters` — extracted sections.
- `GET /api/books/{book_id}/glossary` — per-book and global glossary entries.
- `POST /api/books/{book_id}/glossary` — add a glossary rule (`preserve`, `translate`, `contextual`, or `protect`).
- `PUT /api/books/{book_id}/glossary/{entry_id}` — edit a term belonging to that book.
- `DELETE /api/books/{book_id}/glossary/{entry_id}` — delete a term belonging to that book.
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

The CI suite covers PDF and EPUB import (including EPUB spine reading order), unsupported formats, glossary normalization, duplicate rejection, scoped glossary edit/delete, saved reading position, immutable source text, translation history/restore, reader controls, local-path privacy, and embedded JavaScript syntax. The CI suite also covers scheduled backup timing, retry behavior after a simulated disk-full error, retention and companion-file cleanup, configuration bounds, rollback when a simulated filesystem failure interrupts restore, full recovery of glossary/translation versions/reading progress/source files, and the headless CLI's refusal to create an empty database.

### Optional Windows Task Scheduler integration

Use an installed Python environment that has NovelTrad's project dependencies available. From PowerShell in the repository root, register a per-user task (admin rights are not normally required):

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
.\scripts\install-windows-backup-task.ps1 -PythonExe (Resolve-Path .\.venv\Scripts\python.exe).Path -ProjectRoot (Get-Location).Path
```

The task checks hourly; the app's saved frequency (1–720 hours), enabled flag, and retention count remain authoritative. It works with NovelTrad closed but uses the current user's interactive Windows session, so it does not run while that user is logged out. To remove only the task (not backups or library data):

```powershell
.\scripts\uninstall-windows-backup-task.ps1
```

To test the headless runner manually, run `python -m noveltrad.backup_cli` with the same Python environment and `NOVELTRAD_HOME` used by the app. A missing or corrupt database causes a non-zero exit and no backup is created. The task installation is opt-in; no task is registered automatically.

## Roadmap

1. Harden import and persistence with content validation, scheduled backups, retention, and tested recovery.
2. Finish reader UX: broader accessibility checks, stronger typography/theme controls, and manual Windows verification.
3. Add entity management and translation-memory workflows.
4. Add export validation and a richer EPUB table of contents.
5. Evaluate offline English→Spanish and Japanese→Spanish engines separately; keep rule-based mode distinct from local neural translation.
6. Add contextual prompt generation for user-mediated chat-web assistance.
7. Add versioned translation, quality checks, and TXT/EPUB/PDF export.
8. Package and test the Windows application on a clean machine.
