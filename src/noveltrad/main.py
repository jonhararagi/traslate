from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import zipfile
from contextlib import asynccontextmanager, closing, contextmanager
from functools import wraps
from datetime import datetime, timedelta, timezone
from io import BytesIO
from html import escape as html_escape
from pathlib import Path
import shutil
from typing import Iterator
from uuid import uuid4

import fitz
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

APP_NAME = "NovelTrad"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_EPUB_ENTRIES = 5000
MAX_EPUB_UNCOMPRESSED_BYTES = 500 * 1024 * 1024
MAX_EPUB_COMPRESSION_RATIO = 200
DEFAULT_BACKUP_INTERVAL_HOURS = 24
DEFAULT_BACKUP_RETENTION_COUNT = 14
MIN_BACKUP_INTERVAL_HOURS = 1
MAX_BACKUP_INTERVAL_HOURS = 720
MIN_BACKUP_RETENTION_COUNT = 1
MAX_BACKUP_RETENTION_COUNT = 100
BACKUP_RETRY_BASE_SECONDS = 300
BACKUP_RETRY_MAX_SECONDS = 21600
BACKUP_OPERATION_LOCK = threading.RLock()
_BACKUP_LOCK_LOCAL = threading.local()


@contextmanager
def _cross_process_backup_lock():
    """Acquire an OS-managed lock released automatically if the process exits."""
    lock_path = data_dir() / ".backup-operation.lock"
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            import msvcrt

            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"0")
                lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def serialized_backup_operation(function):
    """Serialize backup, pruning, and restore operations across threads and processes."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        with BACKUP_OPERATION_LOCK:
            depth = getattr(_BACKUP_LOCK_LOCAL, "depth", 0)
            if depth:
                _BACKUP_LOCK_LOCAL.depth = depth + 1
                try:
                    return function(*args, **kwargs)
                finally:
                    _BACKUP_LOCK_LOCAL.depth = depth
            with _cross_process_backup_lock():
                _BACKUP_LOCK_LOCAL.depth = 1
                try:
                    return function(*args, **kwargs)
                finally:
                    del _BACKUP_LOCK_LOCAL.depth
    return wrapped

REQUIRED_BACKUP_TABLES = {"books", "chapters", "glossary_entries", "translation_versions", "corrections"}
ALLOWED_SUFFIXES = {".epub", ".pdf"}


def data_dir() -> Path:
    """Return a per-user data directory; tests can override NOVELTRAD_HOME."""
    override = os.environ.get("NOVELTRAD_HOME")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP_NAME
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "noveltrad"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "noveltrad.sqlite3"


def backup_dir() -> Path:
    path = data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backup_settings_path() -> Path:
    return data_dir() / "backup-settings.json"


def _default_backup_settings() -> dict[str, object]:
    return {
        "enabled": True,
        "interval_hours": DEFAULT_BACKUP_INTERVAL_HOURS,
        "retention_count": DEFAULT_BACKUP_RETENTION_COUNT,
        "last_success_at": None,
        "schedule_started_at": datetime.now(timezone.utc).isoformat(),
        "last_error": None,
        "failure_count": 0,
        "retry_after_at": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_backup_settings() -> dict[str, object]:
    path = backup_settings_path()
    if not path.exists():
        settings = _default_backup_settings()
        save_backup_settings(settings)
        return settings
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("invalid settings")
        enabled = value.get("enabled", True)
        interval = value.get("interval_hours", DEFAULT_BACKUP_INTERVAL_HOURS)
        retention = value.get("retention_count", DEFAULT_BACKUP_RETENTION_COUNT)
        if not isinstance(enabled, bool):
            raise ValueError("invalid enabled")
        if type(interval) is not int or not MIN_BACKUP_INTERVAL_HOURS <= interval <= MAX_BACKUP_INTERVAL_HOURS:
            raise ValueError("invalid interval")
        if type(retention) is not int or not MIN_BACKUP_RETENTION_COUNT <= retention <= MAX_BACKUP_RETENTION_COUNT:
            raise ValueError("invalid retention")
        return {
            "enabled": enabled,
            "interval_hours": interval,
            "retention_count": retention,
            "last_success_at": value.get("last_success_at"),
            "schedule_started_at": value.get("schedule_started_at") or value.get("updated_at"),
            "last_error": value.get("last_error"),
            "failure_count": max(0, int(value.get("failure_count", 0))),
            "retry_after_at": value.get("retry_after_at"),
            "updated_at": value.get("updated_at"),
        }
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        # Fail closed on malformed preferences: disable automation, preserve manual backups.
        return {**_default_backup_settings(), "enabled": False, "last_error": "La configuración de copias está dañada; revisa o restablece backup-settings.json."}


def save_backup_settings(settings: dict[str, object]) -> None:
    path = backup_settings_path()
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    payload = {**settings, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


@serialized_backup_operation
def prune_backups(retention_count: int | None = None) -> list[str]:
    settings = load_backup_settings()
    keep = retention_count if retention_count is not None else int(settings["retention_count"])
    if not MIN_BACKUP_RETENTION_COUNT <= keep <= MAX_BACKUP_RETENTION_COUNT:
        raise ValueError("La retención debe estar entre 1 y 100 copias.")
    backups = sorted(
        (path for path in backup_dir().glob("noveltrad-*.sqlite3") if path.is_file() and not path.is_symlink()),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    removed: list[str] = []
    root = backup_dir()
    for path in backups[keep:]:
        path.unlink(missing_ok=True)
        shutil.rmtree(root / f"{path.stem}-imports", ignore_errors=True)
        removed.append(path.name)

    # Murphy rule: interrupted operations can leave companion folders without
    # their database snapshot. Remove only our own well-formed orphan names.
    live_names = {path.stem for path in root.glob("noveltrad-*.sqlite3")
                  if path.is_file() and not path.is_symlink()}
    orphan_pattern = re.compile(r"noveltrad-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}-imports")
    for candidate in root.iterdir():
        if (candidate.is_dir() and not candidate.is_symlink()
                and orphan_pattern.fullmatch(candidate.name)
                and candidate.name.removesuffix("-imports") not in live_names):
            shutil.rmtree(candidate, ignore_errors=True)

    # Clean staging remnants left by an abrupt process exit; these names are
    # never presented as completed backups.
    for candidate in root.glob(".pending-noveltrad-*"):
        if candidate.is_file() and not candidate.is_symlink():
            candidate.unlink(missing_ok=True)
        elif candidate.is_dir() and not candidate.is_symlink():
            shutil.rmtree(candidate, ignore_errors=True)
    return removed


@serialized_backup_operation
def run_scheduled_backup_if_due(now: datetime | None = None) -> dict[str, object]:
    settings = load_backup_settings()
    if not settings["enabled"]:
        return {"status": "disabled", "created": None}
    current = now or datetime.now(timezone.utc)
    last_success = settings.get("last_success_at")
    baseline = last_success or settings.get("schedule_started_at") or settings.get("updated_at")
    if baseline:
        try:
            due_at = datetime.fromisoformat(str(baseline)) + timedelta(hours=int(settings["interval_hours"]))
            if current < due_at:
                return {"status": "not_due", "created": None, "next_due_at": due_at.isoformat()}
        except (ValueError, TypeError):
            pass
    retry_after = settings.get("retry_after_at")
    if retry_after:
        try:
            retry_at = datetime.fromisoformat(str(retry_after))
            if current < retry_at:
                return {"status": "retry_wait", "created": None, "retry_after_at": retry_at.isoformat(), "error": settings.get("last_error")}
        except (ValueError, TypeError):
            pass
    try:
        path = create_database_backup()
        removed = prune_backups(int(settings["retention_count"]))
        settings["last_success_at"] = current.isoformat()
        settings["last_error"] = None
        settings["failure_count"] = 0
        settings["retry_after_at"] = None
        save_backup_settings(settings)
        return {"status": "created", "created": path.name, "removed": removed, "next_due_at": (current + timedelta(hours=int(settings["interval_hours"]))).isoformat()}
    except Exception as exc:
        failures = int(settings.get("failure_count", 0)) + 1
        delay = min(BACKUP_RETRY_BASE_SECONDS * (2 ** min(failures - 1, 16)), BACKUP_RETRY_MAX_SECONDS)
        settings["failure_count"] = failures
        settings["retry_after_at"] = (current + timedelta(seconds=delay)).isoformat()
        settings["last_error"] = f"{type(exc).__name__}: {exc}"[:1000]
        save_backup_settings(settings)
        return {"status": "error", "created": None, "error": settings["last_error"], "retry_after_at": settings["retry_after_at"], "retry_delay_seconds": delay}


def snapshot_imports_for_backup(backup_path: Path) -> Path:
    """Copy imported source files alongside the database snapshot."""
    source_dir = data_dir() / "imports"
    target_dir = backup_dir() / f"{backup_path.stem}-imports"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    if source_dir.is_dir():
        shutil.copytree(source_dir, target_dir)
    else:
        target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


@serialized_backup_operation
def create_database_backup() -> Path:
    """Publish a backup only after both the SQLite snapshot and originals exist."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir() / f"noveltrad-{stamp}-{uuid4().hex[:8]}.sqlite3"
    staging_db = backup_dir() / f".pending-{target.name}"
    staging_imports = backup_dir() / f"{staging_db.stem}-imports"
    final_imports = backup_dir() / f"{target.stem}-imports"
    try:
        with closing(sqlite3.connect(database_path())) as source, closing(sqlite3.connect(staging_db)) as destination:
            source.backup(destination)
        snapshot_imports_for_backup(staging_db)
        # Publish the companion first and the SQLite file last. Backup listings
        # only match target's public name, so a crash cannot expose a half-backup.
        os.replace(staging_imports, final_imports)
        os.replace(staging_db, target)
    except Exception:
        staging_db.unlink(missing_ok=True)
        shutil.rmtree(staging_imports, ignore_errors=True)
        # Do not remove a previously published backup if a collision ever occurs.
        if not target.exists():
            shutil.rmtree(final_imports, ignore_errors=True)
        raise
    return target

def create_pre_restore_snapshot() -> Path | None:
    """Preserve the current database, even if it is too damaged for SQLite backup."""
    active = database_path()
    if not active.exists():
        return None
    try:
        validate_database_file(active)
        return create_database_backup()
    except ValueError:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = backup_dir() / f"noveltrad-{stamp}-{uuid4().hex[:8]}.sqlite3"
        staging_db = backup_dir() / f".pending-{target.name}"
        staging_imports = backup_dir() / f"{staging_db.stem}-imports"
        final_imports = backup_dir() / f"{target.stem}-imports"
        try:
            shutil.copy2(active, staging_db)
            snapshot_imports_for_backup(staging_db)
            os.replace(staging_imports, final_imports)
            os.replace(staging_db, target)
        except Exception:
            staging_db.unlink(missing_ok=True)
            shutil.rmtree(staging_imports, ignore_errors=True)
            if not target.exists():
                shutil.rmtree(final_imports, ignore_errors=True)
            raise
        return target

def validate_database_file(path: Path) -> None:
    try:
        with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if not integrity or integrity[0] != "ok":
                raise ValueError("La copia de seguridad está dañada.")
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not REQUIRED_BACKUP_TABLES.issubset(tables):
                raise ValueError("El archivo no contiene una base de datos NovelTrad completa.")
    except (sqlite3.DatabaseError, OSError) as exc:
        raise ValueError("No se pudo validar la base de datos de la copia.") from exc


def validate_epub_bytes(raw: bytes) -> None:
    """Reject mislabeled, malformed, or implausibly large EPUB archives before parsing."""
    try:
        with zipfile.ZipFile(BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_EPUB_ENTRIES:
                raise ValueError("El EPUB contiene demasiados archivos internos para importarlo con seguridad.")
            names = {entry.filename for entry in entries}
            if "mimetype" not in names or "META-INF/container.xml" not in names:
                raise ValueError("El archivo ZIP no tiene la estructura obligatoria de un EPUB.")
            mimetype = archive.read("mimetype")
            if mimetype != b"application/epub+zip":
                raise ValueError("El archivo no declara un tipo EPUB válido.")
            total_size = 0
            for entry in entries:
                if entry.flag_bits & 0x1:
                    raise ValueError("No se admiten EPUB con archivos internos cifrados.")
                total_size += entry.file_size
                if entry.file_size and entry.compress_size == 0:
                    raise ValueError("El EPUB contiene una entrada comprimida inválida.")
                if entry.compress_size and entry.file_size / entry.compress_size > MAX_EPUB_COMPRESSION_RATIO:
                    raise ValueError("El EPUB supera el límite de compresión segura.")
            if total_size > MAX_EPUB_UNCOMPRESSED_BYTES:
                raise ValueError("El contenido descomprimido del EPUB supera el límite de 500 MB.")
            bad_entry = archive.testzip()
            if bad_entry:
                raise ValueError("El EPUB está dañado y no supera la verificación interna.")
    except zipfile.BadZipFile as exc:
        raise ValueError("El archivo no es un EPUB ZIP válido o está dañado.") from exc


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_format TEXT NOT NULL CHECK(source_format IN ('epub', 'pdf')),
                source_name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_language TEXT NOT NULL DEFAULT 'und',
                target_language TEXT NOT NULL DEFAULT 'es',
                current_location TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'imported',
                UNIQUE(book_id, chapter_index)
            );
            CREATE TABLE IF NOT EXISTS glossary_entries (
                id TEXT PRIMARY KEY,
                book_id TEXT REFERENCES books(id) ON DELETE CASCADE,
                source_term TEXT NOT NULL,
                preferred_term TEXT NOT NULL,
                rule TEXT NOT NULL CHECK(rule IN ('preserve', 'translate', 'contextual', 'protect')),
                notes TEXT NOT NULL DEFAULT '',
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS translation_versions (
                id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL,
                translated_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(chapter_id, version_number)
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_id TEXT REFERENCES chapters(id) ON DELETE CASCADE,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('segment', 'book', 'global')),
                created_at TEXT NOT NULL
            );
            """
        )


def extract_pdf(path: Path) -> list[tuple[str, str]]:
    chapters: list[tuple[str, str]] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                chapters.append((f"Página {index}", text))
    if not chapters:
        raise ValueError("El PDF no contiene texto seleccionable. El OCR todavía no está disponible en esta versión.")
    return chapters


def extract_epub(path: Path) -> list[tuple[str, str]]:
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    chapters: list[tuple[str, str]] = []
    ordered_items = []
    for spine_entry in book.spine:
        item_id = spine_entry[0] if isinstance(spine_entry, (tuple, list)) else spine_entry
        item = book.get_item_with_id(item_id)
        if item is not None and item.get_type() == ITEM_DOCUMENT:
            ordered_items.append(item)
    if not ordered_items:
        ordered_items = list(book.get_items_of_type(ITEM_DOCUMENT))
    for item in ordered_items:
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for node in soup(["script", "style", "nav"]):
            node.decompose()
        text = "\n\n".join(part.strip() for part in soup.stripped_strings if part.strip())
        if not text:
            continue
        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text(" ", strip=True) if heading else Path(item.get_name()).stem
        chapters.append((title or f"Capítulo {len(chapters) + 1}", text))
    if not chapters:
        raise ValueError("No se encontraron capítulos con texto en este EPUB.")
    return chapters


class BackupSettingsInput(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=DEFAULT_BACKUP_INTERVAL_HOURS, ge=MIN_BACKUP_INTERVAL_HOURS, le=MAX_BACKUP_INTERVAL_HOURS)
    retention_count: int = Field(default=DEFAULT_BACKUP_RETENTION_COUNT, ge=MIN_BACKUP_RETENTION_COUNT, le=MAX_BACKUP_RETENTION_COUNT)


class ProgressInput(BaseModel):
    chapter_index: int = Field(ge=0)
    scroll_top: float = Field(default=0, ge=0, le=100000000)


class TranslationInput(BaseModel):
    translated_text: str = Field(max_length=2_000_000)


class GlossaryInput(BaseModel):
    source_term: str = Field(min_length=1, max_length=300)
    preferred_term: str = Field(min_length=1, max_length=300)
    rule: str = Field(pattern="^(preserve|translate|contextual|protect)$")
    notes: str = Field(default="", max_length=2000)
    approved: bool = False

    @field_validator("source_term", "preferred_term", "notes", mode="before")
    @classmethod
    def strip_text_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class BackupScheduler:
    """Single daemon worker; settings are re-read every tick and shutdown is cooperative."""

    def __init__(self, tick_seconds: float = 30.0):
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="noveltrad-backups", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                run_scheduled_backup_if_due()
            except Exception:
                # A failed scheduled backup must not terminate the service worker.
                pass
            if self._stop.wait(self.tick_seconds):
                break


backup_scheduler = BackupScheduler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    recover_interrupted_restore()
    init_db()
    load_backup_settings()
    backup_scheduler.start()
    try:
        yield
    finally:
        backup_scheduler.stop()


app = FastAPI(title=APP_NAME, version="0.1.0", docs_url="/api/docs", lifespan=lifespan)


@app.post("/api/backups")
@serialized_backup_operation
def create_backup() -> dict[str, object]:
    init_db()
    path = create_database_backup()
    settings = load_backup_settings()
    removed = prune_backups(int(settings["retention_count"]))
    return {"name": path.name, "size_bytes": path.stat().st_size, "created": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), "removed_backups": removed}


@app.get("/api/backups/settings")
def get_backup_settings() -> dict[str, object]:
    return load_backup_settings()


@app.put("/api/backups/settings")
@serialized_backup_operation
def update_backup_settings(payload: BackupSettingsInput) -> dict[str, object]:
    current = load_backup_settings()
    updated = {
        **current,
        "enabled": payload.enabled,
        "interval_hours": payload.interval_hours,
        "retention_count": payload.retention_count,
        "schedule_started_at": current.get("schedule_started_at") or datetime.now(timezone.utc).isoformat(),
        "last_error": None,
    }
    save_backup_settings(updated)
    removed = prune_backups(payload.retention_count)
    return {**load_backup_settings(), "removed_backups": removed}


@app.post("/api/backups/prune")
@serialized_backup_operation
def prune_backup_endpoint() -> dict[str, object]:
    settings = load_backup_settings()
    removed = prune_backups(int(settings["retention_count"]))
    return {"removed": removed, "retained_count": len(list(backup_dir().glob("noveltrad-*.sqlite3")))}


@app.get("/api/backups")
def list_backups() -> list[dict[str, object]]:
    backups = []
    for path in sorted(backup_dir().glob("noveltrad-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        backups.append({"name": path.name, "size_bytes": path.stat().st_size, "created": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()})
    return backups


def _restore_transaction_path() -> Path:
    return data_dir() / ".restore-transaction.json"


def _write_restore_transaction(transaction: dict[str, object]) -> None:
    """Persist a rollback journal before mutating the live database or imports."""
    path = _restore_transaction_path()
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(transaction, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def recover_interrupted_restore() -> bool:
    """Recover an interrupted restore without letting a corrupt safety copy block startup."""
    journal = _restore_transaction_path()
    if not journal.exists():
        return False
    try:
        transaction = json.loads(journal.read_text(encoding="utf-8"))
        if not isinstance(transaction, dict):
            raise ValueError("El diario de restauración no es válido.")
        previous_name = transaction.get("previous_imports")
        if (not isinstance(previous_name, str)
                or not re.fullmatch(r"imports-before-restore-[0-9a-f]{32}", previous_name)):
            raise ValueError("La ruta de recuperación de archivos no es válida.")
        safety_name = transaction.get("safety_backup")
        database_existed = transaction.get("database_existed")
        imports_snapshot_present = transaction.get("imports_snapshot_present")
        imports_directory_existed = transaction.get("imports_directory_existed")
        if (not isinstance(database_existed, bool)
                or not isinstance(imports_snapshot_present, bool)
                or not isinstance(imports_directory_existed, bool)):
            raise ValueError("El diario de restauración está incompleto.")
        previous_imports = data_dir() / previous_name
        imports_dir = data_dir() / "imports"
        restore_already_committed = False

        if safety_name is not None:
            if (not isinstance(safety_name, str)
                    or not re.fullmatch(r"noveltrad-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\.sqlite3", safety_name)):
                raise ValueError("La copia de recuperación indicada no es válida.")
            safety_path = backup_dir() / safety_name
            if not safety_path.is_file():
                raise ValueError("No se encuentra la copia previa necesaria para recuperar la restauración.")
            try:
                validate_database_file(safety_path)
            except ValueError:
                # If the pre-restore database was already corrupt, its safety
                # copy is not a rollback candidate. A crash may have happened
                # after the valid target DB was atomically installed; preserve
                # that valid DB and its matching imported originals instead.
                validate_database_file(database_path())
                restore_already_committed = True

            if not restore_already_committed:
                recovered_db = data_dir() / f"restore-recovery-{uuid4().hex}.sqlite3"
                try:
                    with closing(sqlite3.connect(f"file:{safety_path.as_posix()}?mode=ro", uri=True)) as source, closing(sqlite3.connect(recovered_db)) as destination:
                        source.backup(destination)
                    validate_database_file(recovered_db)
                    os.replace(recovered_db, database_path())
                finally:
                    recovered_db.unlink(missing_ok=True)
        elif not database_existed:
            database_path().unlink(missing_ok=True)

        if imports_snapshot_present:
            if restore_already_committed:
                # The target's imports were swapped before its database. Keep
                # them together and discard the old directory left by the crash.
                shutil.rmtree(previous_imports, ignore_errors=True)
            elif previous_imports.exists():
                if imports_dir.exists():
                    shutil.rmtree(imports_dir)
                os.replace(previous_imports, imports_dir)
            elif not imports_directory_existed and imports_dir.exists():
                shutil.rmtree(imports_dir)
        journal.unlink()
        if os.name != "nt":
            directory_fd = os.open(journal.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        for path in data_dir().glob("restore-imports-*"):
            shutil.rmtree(path, ignore_errors=True)
        for path in data_dir().glob("restore-*.sqlite3"):
            path.unlink(missing_ok=True)
        return True
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "No se pudo recuperar una restauración interrumpida; se conserva el diario para reintentar sin abrir la biblioteca."
        ) from exc

@app.post("/api/backups/{backup_name}/restore")
@serialized_backup_operation
def restore_backup(backup_name: str) -> dict[str, object]:
    if not re.fullmatch(r"noveltrad-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}\.sqlite3", backup_name):
        raise HTTPException(status_code=400, detail="Nombre de copia no válido.")
    root = backup_dir().resolve()
    source_path = (root / backup_name).resolve()
    if source_path.parent != root or not source_path.is_file():
        raise HTTPException(status_code=404, detail="No se encontró la copia de seguridad.")

    staging = data_dir() / f"restore-{uuid4().hex}.sqlite3"
    staged_imports = data_dir() / f"restore-imports-{uuid4().hex}"
    previous_imports = data_dir() / f"imports-before-restore-{uuid4().hex}"
    imports_snapshot = root / f"{Path(backup_name).stem}-imports"
    journal = _restore_transaction_path()
    swapped_imports = False
    transaction_written = False
    safety_copy = None
    try:
        validate_database_file(source_path)
        with closing(sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)) as source, closing(sqlite3.connect(staging)) as destination:
            source.backup(destination)
        validate_database_file(staging)
        if imports_snapshot.exists():
            if (not imports_snapshot.is_dir() or imports_snapshot.is_symlink()
                    or imports_snapshot.resolve().parent != root):
                raise ValueError("La copia de archivos originales tiene una estructura no válida.")
            if any(path.is_symlink() or not path.is_file() for path in imports_snapshot.rglob("*")):
                raise ValueError("La copia contiene archivos originales no válidos.")
            shutil.copytree(imports_snapshot, staged_imports)
        safety_copy = create_pre_restore_snapshot()
        imports_dir = data_dir() / "imports"
        database_existed = database_path().exists()
        if database_existed and safety_copy is None:
            raise OSError("No se pudo crear la copia de seguridad previa a la restauración.")
        _write_restore_transaction({
            "version": 1,
            "safety_backup": safety_copy.name if safety_copy else None,
            "database_existed": database_existed,
            "previous_imports": previous_imports.name,
            "imports_snapshot_present": imports_snapshot.exists(),
            "imports_directory_existed": imports_dir.exists(),
        })
        transaction_written = True
        if imports_snapshot.exists():
            if imports_dir.exists():
                os.replace(imports_dir, previous_imports)
            try:
                os.replace(staged_imports, imports_dir)
                swapped_imports = True
            except OSError:
                if previous_imports.exists() and not imports_dir.exists():
                    os.replace(previous_imports, imports_dir)
                raise
        try:
            os.replace(staging, database_path())
        except OSError:
            if swapped_imports:
                shutil.rmtree(imports_dir, ignore_errors=True)
                if previous_imports.exists():
                    os.replace(previous_imports, imports_dir)
            raise
        journal.unlink(missing_ok=True)
        if os.name != "nt":
            directory_fd = os.open(journal.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        if previous_imports.exists():
            shutil.rmtree(previous_imports, ignore_errors=True)
        return {"restored": True, "backup_name": backup_name, "safety_backup": safety_copy.name if safety_copy else None,
                "source_files_restored": bool(imports_snapshot.exists())}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (sqlite3.DatabaseError, OSError) as exc:
        if transaction_written:
            try:
                recover_interrupted_restore()
            except RuntimeError:
                pass
        raise HTTPException(status_code=500, detail="No se pudo restaurar la copia. Se intentó recuperar el estado anterior mediante el diario transaccional y la copia de seguridad automática.") from exc
    finally:
        staging.unlink(missing_ok=True)
        shutil.rmtree(staged_imports, ignore_errors=True)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"app": APP_NAME, "status": "ok", "mode": "local-first", "translation_engine": "not-configured"}


@app.get("/api/books")
def list_books() -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        rows = conn.execute(
            "SELECT b.id, b.title, b.source_format, b.source_name, b.source_language, "
            "b.target_language, b.current_location, b.created_at, COUNT(c.id) AS chapter_count FROM books b "
            "LEFT JOIN chapters c ON c.book_id = b.id GROUP BY b.id ORDER BY b.created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/books/import")
async def import_book(file: UploadFile = File(...)) -> dict[str, object]:
    init_db()
    filename = Path(file.filename or "book").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Solo se admiten archivos EPUB y PDF.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El límite de importación es 100 MB por archivo.")

    if suffix == ".pdf":
        if b"%PDF-" not in raw[:1024]:
            raise HTTPException(status_code=415, detail="La extensión es PDF, pero el contenido no tiene una cabecera PDF válida.")
    else:
        try:
            validate_epub_bytes(raw)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    book_id = str(uuid4())
    safe_name = f"{book_id}{suffix}"
    source_path = data_dir() / "imports" / safe_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(raw)
    try:
        chapters = extract_epub(source_path) if suffix == ".epub" else extract_pdf(source_path)
    except Exception as exc:
        source_path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail="No se pudo leer el archivo. Comprueba que no esté dañado o protegido.") from exc

    title = Path(filename).stem
    now = datetime.now(timezone.utc).isoformat()
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
                (book_id, title, suffix[1:], filename, str(source_path), now),
            )
            conn.executemany(
                "INSERT INTO chapters(id,book_id,chapter_index,title,original_text) VALUES(?,?,?,?,?)",
                [(str(uuid4()), book_id, index, chapter_title, text) for index, (chapter_title, text) in enumerate(chapters)],
            )
    except Exception:
        source_path.unlink(missing_ok=True)
        raise
    return {"id": book_id, "title": title, "format": suffix[1:], "chapter_count": len(chapters), "status": "imported"}


@app.get("/api/books/{book_id}/chapters")
def list_chapters(book_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        rows = conn.execute(
            "SELECT id, book_id, chapter_index, title, original_text, translated_text, status "
            "FROM chapters WHERE book_id = ? ORDER BY chapter_index", (book_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/books/{book_id}/export/epub")
def export_translated_epub(book_id: str) -> StreamingResponse:
    init_db()
    with connection() as conn:
        book = conn.execute("SELECT title FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        chapters = conn.execute(
            "SELECT title, translated_text FROM chapters WHERE book_id = ? ORDER BY chapter_index",
            (book_id,),
        ).fetchall()
        missing = sum(1 for chapter in chapters if not chapter["translated_text"].strip())
        if not chapters:
            raise HTTPException(status_code=422, detail="La novela no contiene capítulos exportables.")
        if missing:
            raise HTTPException(
                status_code=409,
                detail=f"No se puede exportar todavía: hay {missing} capítulo(s) sin traducir. Completa las traducciones para evitar omisiones.",
            )

    output_book = epub.EpubBook()
    output_book.set_identifier(str(uuid4()))
    output_book.set_title(book["title"])
    output_book.set_language("es")
    output_chapters = []
    for index, chapter in enumerate(chapters, start=1):
        document = epub.EpubHtml(
            title=chapter["title"] or f"Capítulo {index}",
            file_name=f"chapter_{index:04d}.xhtml",
            lang="es",
        )
        paragraphs = "".join(
            f"<p>{html_escape(paragraph)}</p>"
            for paragraph in chapter["translated_text"].splitlines()
            if paragraph.strip()
        )
        document.content = (
            "<!DOCTYPE html><html xmlns='http://www.w3.org/1999/xhtml' lang='es'>"
            f"<head><title>{html_escape(chapter['title'])}</title></head>"
            f"<body><h1>{html_escape(chapter['title'])}</h1>{paragraphs}</body></html>"
        )
        output_book.add_item(document)
        output_chapters.append(document)
    output_book.add_item(epub.EpubNcx())
    output_book.add_item(epub.EpubNav())
    output_book.spine = ["nav", *output_chapters]
    output_buffer = BytesIO()
    epub.write_epub(output_buffer, output_book)
    safe_title = re.sub(r"[^A-Za-z0-9._-]+", "_", book["title"]).strip("._") or "noveltrad"
    return StreamingResponse(
        iter([output_buffer.getvalue()]),
        media_type="application/epub+zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}-es.epub"'},
    )


@app.get("/api/books/{book_id}/glossary")
def list_glossary(book_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        rows = conn.execute(
            "SELECT id, book_id, source_term, preferred_term, rule, notes, approved FROM glossary_entries "
            "WHERE book_id = ? OR book_id IS NULL ORDER BY source_term COLLATE NOCASE", (book_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.put("/api/books/{book_id}/glossary/{entry_id}")
def update_glossary_entry(book_id: str, entry_id: str, entry: GlossaryInput) -> dict[str, object]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        existing = conn.execute(
            "SELECT id FROM glossary_entries WHERE id = ? AND book_id = ?", (entry_id, book_id)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="No se encontró el término en esta novela.")
        duplicate = conn.execute(
            "SELECT 1 FROM glossary_entries WHERE book_id = ? AND source_term = ? COLLATE NOCASE AND id != ?",
            (book_id, entry.source_term, entry_id),
        ).fetchone()
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe otro término con ese nombre en esta novela.")
        conn.execute(
            "UPDATE glossary_entries SET source_term = ?, preferred_term = ?, rule = ?, notes = ?, approved = ? "
            "WHERE id = ? AND book_id = ?",
            (entry.source_term, entry.preferred_term, entry.rule, entry.notes, int(entry.approved), entry_id, book_id),
        )
    return {"id": entry_id, **entry.model_dump()}


@app.delete("/api/books/{book_id}/glossary/{entry_id}")
def delete_glossary_entry(book_id: str, entry_id: str) -> dict[str, object]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        cursor = conn.execute(
            "DELETE FROM glossary_entries WHERE id = ? AND book_id = ?", (entry_id, book_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se encontró el término en esta novela.")
    return {"id": entry_id, "deleted": True}


@app.post("/api/books/{book_id}/glossary")
def add_glossary_entry(book_id: str, entry: GlossaryInput) -> dict[str, object]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        duplicate = conn.execute(
            "SELECT 1 FROM glossary_entries WHERE book_id = ? AND source_term = ? COLLATE NOCASE",
            (book_id, entry.source_term),
        ).fetchone()
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail="Ese término ya existe en el glosario de esta novela. Edita la entrada existente para cambiar su regla.",
            )
        entry_id = str(uuid4())
        conn.execute(
            "INSERT INTO glossary_entries(id,book_id,source_term,preferred_term,rule,notes,approved,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (entry_id, book_id, entry.source_term.strip(), entry.preferred_term.strip(), entry.rule,
             entry.notes.strip(), int(entry.approved), datetime.now(timezone.utc).isoformat()),
        )
    return {"id": entry_id, **entry.model_dump()}


@app.put("/api/books/{book_id}/progress")
def save_progress(book_id: str, progress: ProgressInput) -> dict[str, object]:
    init_db()
    with connection() as conn:
        book = conn.execute("SELECT id FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        chapter = conn.execute(
            "SELECT 1 FROM chapters WHERE book_id = ? AND chapter_index = ?",
            (book_id, progress.chapter_index),
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=422, detail="El capítulo indicado no existe en esta novela.")
        location = json.dumps(
            {"chapter_index": progress.chapter_index, "scroll_top": progress.scroll_top},
            separators=(",", ":"),
        )
        conn.execute("UPDATE books SET current_location = ? WHERE id = ?", (location, book_id))
    return {"book_id": book_id, **progress.model_dump(), "saved": True}


@app.put("/api/chapters/{chapter_id}/translation")
def save_translation(chapter_id: str, translation: TranslationInput) -> dict[str, object]:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        chapter = conn.execute(
            "SELECT id, translated_text FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        current = chapter["translated_text"]
        if current != translation.translated_text:
            version = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version "
                "FROM translation_versions WHERE chapter_id = ?", (chapter_id,)
            ).fetchone()["next_version"]
            conn.execute(
                "INSERT INTO translation_versions(id, chapter_id, version_number, translated_text, created_at) "
                "VALUES(?,?,?,?,?)",
                (str(uuid4()), chapter_id, version, current, now),
            )
            conn.execute(
                "UPDATE chapters SET translated_text = ?, status = ? WHERE id = ?",
                (translation.translated_text, "translated" if translation.translated_text.strip() else "imported", chapter_id),
            )
        return {"chapter_id": chapter_id, "translated_text": translation.translated_text, "saved": True}


@app.get("/api/chapters/{chapter_id}/translation/versions")
def translation_versions(chapter_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM chapters WHERE id = ?", (chapter_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        rows = conn.execute(
            "SELECT version_number, translated_text, created_at FROM translation_versions "
            "WHERE chapter_id = ? ORDER BY version_number DESC", (chapter_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/chapters/{chapter_id}/translation/restore/{version_number}")
def restore_translation_version(chapter_id: str, version_number: int) -> dict[str, object]:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        chapter = conn.execute(
            "SELECT id, translated_text FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        target = conn.execute(
            "SELECT translated_text FROM translation_versions WHERE chapter_id = ? AND version_number = ?",
            (chapter_id, version_number),
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="No se encontró esa versión de la traducción.")
        next_version = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version "
            "FROM translation_versions WHERE chapter_id = ?", (chapter_id,)
        ).fetchone()["next_version"]
        conn.execute(
            "INSERT INTO translation_versions(id, chapter_id, version_number, translated_text, created_at) "
            "VALUES(?,?,?,?,?)",
            (str(uuid4()), chapter_id, next_version, chapter["translated_text"], now),
        )
        restored = target["translated_text"]
        conn.execute(
            "UPDATE chapters SET translated_text = ?, status = ? WHERE id = ?",
            (restored, "translated" if restored.strip() else "imported", chapter_id),
        )
    return {"chapter_id": chapter_id, "version_number": version_number, "translated_text": restored, "restored": True}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NovelTrad — Tu biblioteca</title><style>
:root{color-scheme:light dark;--bg:#f5f0e8;--panel:#fffdf8;--ink:#28251f;--muted:#777064;--accent:#6b5a9e;--line:#e4ddd1;--soft:#eee8f8}
@media(prefers-color-scheme:dark){:root{--bg:#191a20;--panel:#23252d;--ink:#ece9e2;--muted:#aaa6b0;--accent:#c0b2ff;--line:#393b46;--soft:#34303f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}button,input,textarea{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid var(--accent);outline-offset:3px}main{max-width:1120px;margin:auto;padding:24px 20px 60px}.top{display:flex;align-items:center;gap:12px;margin-bottom:28px}.mark{background:var(--accent);color:white;border-radius:14px;padding:9px 12px;font-weight:800}.sub{color:var(--muted)}h1{font-size:clamp(1.8rem,5vw,2.6rem);line-height:1.15;margin:.2rem 0}h2{margin-top:0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 6px 24px #00000008}.primary,.secondary,.quiet{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:12px;padding:10px 15px;font-weight:650}.primary{background:var(--accent);color:white}.secondary{background:var(--soft);color:var(--ink)}.quiet{background:transparent;color:var(--ink);border:1px solid var(--line)}input[type=file]{max-width:100%;margin:12px 0}.book{display:flex;align-items:center;gap:16px;padding:16px 0;border-bottom:1px solid var(--line)}.book:last-child{border:0}.bookinfo{flex:1;min-width:0}.empty{padding:24px;text-align:center;color:var(--muted)}#status{margin-top:12px;min-height:1.5em}.pill{font-size:.8rem;border:1px solid var(--line);border-radius:99px;padding:3px 9px;color:var(--muted)}#reader{display:none}.reader-head{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}.reader-head h2{margin:0;flex:1}.reader-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.reader-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.reading-pane{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}.reading-pane h3{margin-top:0}.original-text{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto;font-family:Georgia,'Times New Roman',serif;line-height:1.85;font-size:19px}.translation-text{width:100%;min-height:48vh;resize:vertical;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--ink);line-height:1.85;font-family:Georgia,'Times New Roman',serif;font-size:19px}.chapter-nav{display:flex;gap:8px;align-items:center;justify-content:space-between;margin:14px 0}.chapter-nav select{max-width:65%;padding:8px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}.reader-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}.small{font-size:.9rem}.hidden{display:none!important}@media(max-width:760px){main{padding:18px 12px 40px}.reader-grid{grid-template-columns:1fr}.original-text{max-height:45vh}.translation-text{min-height:35vh}.panel{padding:16px}.book{align-items:flex-start;flex-wrap:wrap}.bookinfo{flex-basis:60%}}
</style></head><body><main>
<header class="top"><div class="mark">NT</div><div><strong>NovelTrad</strong><div class="sub">Tu biblioteca, tus reglas, tu espacio</div></div><span style="margin-left:auto" class="pill">Local-first</span></header>
<section id="library"><h1>Volvé a tu historia.</h1><p class="sub">Un espacio tranquilo para leer y preparar tus traducciones. Tus libros se guardan en este equipo.</p>
<section class="panel"><h2>Importar una novela</h2><p class="sub">Solo EPUB y PDF · Máximo 100 MB. Los PDF escaneados todavía necesitan OCR.</p><form id="upload"><input id="file" name="file" type="file" accept=".epub,.pdf,application/pdf,application/epub+zip" required><br><button class="primary" type="submit">Añadir a mi biblioteca</button></form><div id="status" role="status" aria-live="polite"></div></section>
<section class="panel"><h2>Mi biblioteca</h2><div id="books" class="empty">Cargando biblioteca…</div></section>
<section class="panel"><h2>Copias de seguridad</h2><p class="sub">Guarda el estado de tu biblioteca y permite recuperarlo. Antes de restaurar se crea otra copia de seguridad automática.</p><div class="reader-actions"><button id="create-backup" class="secondary" type="button">Crear copia ahora</button><button id="refresh-backups" class="quiet" type="button">Actualizar lista</button></div><label class="small" for="backup-select">Copia disponible</label><select id="backup-select" style="width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)"><option value="">Todavía no hay copias</option></select><button id="restore-backup" class="secondary" type="button" disabled>Restaurar copia seleccionada</button><div id="backup-status" role="status" aria-live="polite"></div></section>
<section class="panel"><h2>Copias automáticas</h2><p class="sub">La aplicación crea copias en segundo plano mientras está abierta. La programación y la retención se guardan en este equipo.</p><label><input id="backup-enabled" type="checkbox" checked> Activar copias automáticas</label><div class="reader-actions"><label for="backup-interval">Frecuencia (horas)<input id="backup-interval" type="number" min="1" max="720" value="24" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)"></label><label for="backup-retention">Copias a conservar<input id="backup-retention" type="number" min="1" max="100" value="14" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)"></label></div><button id="save-backup-settings" class="secondary" type="button">Guardar programación</button><button id="prune-backups" class="quiet" type="button">Aplicar retención ahora</button><div id="backup-settings-status" role="status" aria-live="polite"></div></section></section>
<section id="reader"><div class="reader-head"><button id="back" class="quiet" type="button">← Biblioteca</button><h2 id="book-title">Leyendo</h2><button id="toggle-glossary" class="secondary" type="button">Glosario</button><label class="small">Texto <select id="font-size" aria-label="Tamaño del texto"><option value="17">Pequeño</option><option value="19" selected>Mediano</option><option value="22">Grande</option><option value="26">Muy grande</option></select></label></div>
<div class="chapter-nav"><button id="previous" class="secondary" type="button">← Anterior</button><select id="chapter-select" aria-label="Elegir capítulo"></select><button id="next" class="secondary" type="button">Siguiente →</button></div>
<div class="reader-grid"><section class="reading-pane"><h3>Original</h3><div id="original" class="original-text" tabindex="0"></div></section><section class="reading-pane"><h3>Traducción</h3><p class="sub small">El original permanece intacto. Tus cambios se guardan aparte.</p><textarea id="translation" class="translation-text" aria-label="Texto de traducción" placeholder="Escribí o pegá aquí tu traducción…"></textarea><div class="reader-actions"><button id="save-translation" class="primary" type="button">Guardar traducción</button><button id="export-epub" class="secondary" type="button">Exportar EPUB</button><button id="show-history" class="secondary" type="button">Historial</button><span id="save-status" class="sub small" role="status" aria-live="polite"></span></div><p class="sub small">Cada guardado conserva una versión anterior.</p><div id="translation-history" class="hidden"><h4>Versiones guardadas</h4><div id="history-list"></div><p id="history-status" class="sub small" role="status" aria-live="polite"></p></div></section></div>
<section id="glossary-panel" class="panel hidden"><div class="reader-head"><h2>Glosario de esta novela</h2><button id="close-glossary" class="quiet" type="button">Cerrar</button></div><p class="sub small">Protegé nombres y fijá términos para mantener la coherencia. Las reglas se guardan por novela.</p><form id="glossary-form"><div class="reader-grid"><label>Término original<input id="glossary-source" required maxlength="300" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Oknodie"></label><label>Forma preferida<input id="glossary-target" required maxlength="300" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Oknodie"></label></div><div class="reader-actions"><label>Regla <select id="glossary-rule" style="padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)"><option value="protect">Proteger nombre/término</option><option value="preserve">Conservar exactamente</option><option value="translate">Traducir siempre así</option><option value="contextual">Depende del contexto</option></select></label><label><input id="glossary-approved" type="checkbox"> Aprobado</label><button id="glossary-submit" class="primary" type="submit">Guardar término</button><button id="glossary-cancel" class="secondary hidden" type="button">Cancelar edición</button></div><label>Notas opcionales<textarea id="glossary-notes" rows="2" maxlength="2000" style="display:block;width:100%;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Nombre propio; no traducir."></textarea></label><p id="glossary-status" class="sub small" role="status" aria-live="polite"></p></form><div id="glossary-list"></div></section>
</section><p class="sub small">El motor de traducción automática todavía no está configurado. Esta versión permite leer, guardar traducciones propias y retomar el progreso.</p></main>
<script>
const $=s=>document.querySelector(s);let currentBook=null,chapters=[],chapterPos=0,saveTimer=null,translationDirty=false,editingGlossaryId=null;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function api(url,options={}){const r=await fetch(url,options);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||'No se pudo completar la operación');return d}
async function refresh(){try{const books=await api('/api/books');$('#books').className=books.length?'':'empty';$('#books').innerHTML=books.length?books.map(b=>{let pos={};try{pos=JSON.parse(b.current_location||'{}')}catch{}return '<article class="book"><div class="bookinfo"><strong>'+esc(b.title)+'</strong><div class="sub small">'+b.chapter_count+' secciones · '+esc(b.source_format.toUpperCase())+' · Progreso guardado</div></div><button class="primary" type="button" data-open="'+esc(b.id)+'" data-chapter="'+(Number.isInteger(pos.chapter_index)?pos.chapter_index:0)+'">Abrir novela</button></article>'}).join(''):'<div class="empty">Todavía no hay novelas. Importá un EPUB o PDF para empezar.</div>'}catch(e){$('#books').textContent=e.message}}
$('#books').addEventListener('click',e=>{const b=e.target.closest('[data-open]');if(b)openBook(b.dataset.open,Number(b.dataset.chapter)||0)});
loadBackups();
loadBackupSettings();
async function loadBackupSettings(){try{const s=await api('/api/backups/settings');$('#backup-enabled').checked=s.enabled;$('#backup-interval').value=s.interval_hours;$('#backup-retention').value=s.retention_count;const status=[];status.push(s.enabled?'Copias automáticas activadas':'Copias automáticas desactivadas');status.push('Frecuencia: cada '+s.interval_hours+' h');status.push('Retención: '+s.retention_count+' copias');if(s.last_success_at)status.push('Última copia automática correcta: '+new Date(s.last_success_at).toLocaleString());if(s.last_error)status.push('Último error: '+s.last_error);$('#backup-settings-status').textContent=status.join(' · ')}catch(e){$('#backup-settings-status').textContent='No se pudo cargar la programación: '+e.message}}
$('#save-backup-settings').addEventListener('click',async()=>{const button=$('#save-backup-settings');const interval=Number($('#backup-interval').value),retention=Number($('#backup-retention').value);if(!Number.isInteger(interval)||interval<1||interval>720||!Number.isInteger(retention)||retention<1||retention>100){$('#backup-settings-status').textContent='La frecuencia debe ser de 1 a 720 horas y la retención de 1 a 100 copias.';return}button.disabled=true;try{const s=await api('/api/backups/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:$('#backup-enabled').checked,interval_hours:interval,retention_count:retention})});$('#backup-settings-status').textContent='Programación guardada. '+(s.removed_backups.length?'Copias eliminadas por retención: '+s.removed_backups.length+'.':'No fue necesario eliminar copias.');await loadBackups();await loadBackupSettings()}catch(e){$('#backup-settings-status').textContent='No se pudo guardar: '+e.message}finally{button.disabled=false}});
$('#prune-backups').addEventListener('click',async()=>{const button=$('#prune-backups');button.disabled=true;try{const r=await api('/api/backups/prune',{method:'POST'});$('#backup-settings-status').textContent='Retención aplicada: '+r.removed.length+' copia(s) eliminada(s); quedan '+r.retained_count+'.';await loadBackups()}catch(e){$('#backup-settings-status').textContent='No se pudo aplicar la retención: '+e.message}finally{button.disabled=false}});
async function loadBackups(){try{const backups=await api('/api/backups');const select=$('#backup-select');select.innerHTML=backups.length?backups.map(b=>'<option value="'+esc(b.name)+'">'+esc(b.name)+' · '+(b.size_bytes/1024).toFixed(1)+' KB</option>').join(''):'<option value="">Todavía no hay copias</option>';$('#restore-backup').disabled=!backups.length;$('#backup-status').textContent=backups.length?backups.length+' copia(s) disponible(s).':'No hay copias de seguridad guardadas.'}catch(e){$('#backup-status').textContent='No se pudo cargar la lista: '+e.message}}
$('#create-backup').addEventListener('click',async()=>{const button=$('#create-backup');button.disabled=true;$('#backup-status').textContent='Creando una copia consistente…';try{const backup=await api('/api/backups',{method:'POST'});$('#backup-status').textContent='Copia creada: '+backup.name+' ('+(backup.size_bytes/1024).toFixed(1)+' KB).';await loadBackups()}catch(e){$('#backup-status').textContent='Error: '+e.message}finally{button.disabled=false}});
$('#refresh-backups').addEventListener('click',loadBackups);
$('#restore-backup').addEventListener('click',async()=>{const name=$('#backup-select').value;if(!name)return;if(!confirm('La restauración reemplazará la biblioteca actual con el estado de esta copia. Antes se guardará una copia de seguridad del estado actual. ¿Continuar?'))return;const button=$('#restore-backup');button.disabled=true;$('#backup-status').textContent='Validando y restaurando…';try{const result=await api('/api/backups/'+encodeURIComponent(name)+'/restore',{method:'POST'});$('#backup-status').textContent='Biblioteca restaurada. Copia de seguridad del estado anterior: '+result.safety_backup+'.';await refresh();await loadBackups()}catch(e){$('#backup-status').textContent='No se pudo restaurar: '+e.message}finally{button.disabled=false}});

$('#upload').addEventListener('submit',async e=>{e.preventDefault();const file=$('#file').files[0];if(!file)return;$('#status').textContent='Importando y preparando el libro…';const data=new FormData();data.append('file',file);try{const result=await api('/api/books/import',{method:'POST',body:data});$('#status').textContent='“'+result.title+'” se importó correctamente ('+result.chapter_count+' secciones).';e.target.reset();await refresh()}catch(err){$('#status').textContent=err.message}});
async function openBook(id,preferred=0){try{const books=await api('/api/books');currentBook=books.find(b=>b.id===id);if(!currentBook)throw new Error('No se encontró la novela');chapters=await api('/api/books/'+id+'/chapters');if(!chapters.length)throw new Error('La novela no contiene secciones legibles');chapterPos=Math.max(0,Math.min(preferred,chapters.length-1));$('#book-title').textContent=currentBook.title;$('#chapter-select').innerHTML=chapters.map((c,i)=>'<option value="'+i+'">'+(i+1)+'. '+esc(c.title)+'</option>').join('');$('#library').classList.add('hidden');$('#reader').style.display='block';renderChapter(true)}catch(e){$('#status').textContent=e.message}}
function renderChapter(restore){const c=chapters[chapterPos];if(!c)return;translationDirty=false;$('#chapter-select').value=String(chapterPos);$('#original').textContent=c.original_text;$('#translation').value=c.translated_text||'';$('#previous').disabled=chapterPos===0;$('#next').disabled=chapterPos===chapters.length-1;$('#save-status').textContent='';$('#original').scrollTop=0;if(restore){let p={};try{p=JSON.parse(currentBook.current_location||'{}')}catch{}if(p.chapter_index===chapterPos&&Number.isFinite(p.scroll_top))$('#original').scrollTop=p.scroll_top}saveProgress()}
function goToChapter(i){if(i<0||i>=chapters.length)return;if(translationDirty&&!confirm('Hay cambios de traducción sin guardar. ¿Descartarlos y cambiar de capítulo?'))return;translationDirty=false;chapterPos=i;renderChapter(false)}
$('#chapter-select').addEventListener('change',e=>goToChapter(Number(e.target.value)));$('#previous').addEventListener('click',()=>goToChapter(chapterPos-1));$('#next').addEventListener('click',()=>goToChapter(chapterPos+1));
async function persistProgressNow(){if(!currentBook)return;clearTimeout(saveTimer);const scroll_top=$('#original').scrollTop;await api('/api/books/'+currentBook.id+'/progress',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter_index:chapterPos,scroll_top})});currentBook.current_location=JSON.stringify({chapter_index:chapterPos,scroll_top})}
function saveProgress(){if(!currentBook)return;clearTimeout(saveTimer);saveTimer=setTimeout(async()=>{try{await persistProgressNow()}catch(e){$('#save-status').textContent='No se pudo guardar el progreso: '+e.message}},250)}
$('#original').addEventListener('scroll',saveProgress);
$('#export-epub').addEventListener('click',async()=>{if(!currentBook)return;const button=$('#export-epub');button.disabled=true;$('#save-status').textContent='Preparando EPUB…';try{const response=await fetch('/api/books/'+currentBook.id+'/export/epub');let result={};if(!response.ok){try{result=await response.json()}catch{}throw new Error(result.detail||'No se pudo exportar el EPUB')}const blob=await response.blob();const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download=(currentBook.title||'NovelTrad')+'-es.epub';document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);$('#save-status').textContent='EPUB de traducción exportado.'}catch(e){$('#save-status').textContent='Exportación: '+e.message}finally{button.disabled=false}});
$('#save-translation').addEventListener('click',async()=>{const c=chapters[chapterPos];$('#save-status').textContent='Guardando…';try{const result=await api('/api/chapters/'+c.id+'/translation',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({translated_text:$('#translation').value})});c.translated_text=result.translated_text;translationDirty=false;$('#save-status').textContent='Guardado en este equipo.'}catch(e){$('#save-status').textContent='Error: '+e.message}});
async function loadHistory(){const c=chapters[chapterPos];try{const versions=await api('/api/chapters/'+c.id+'/translation/versions');$('#history-list').innerHTML=versions.length?versions.map(v=>'<article class="book"><div class="bookinfo"><strong>Versión '+v.version_number+'</strong><div class="sub small">'+esc(v.created_at)+'</div><div style="white-space:pre-wrap;overflow-wrap:anywhere;margin-top:6px">'+esc(v.translated_text||'(Traducción vacía)')+'</div></div><button class="secondary" type="button" data-restore="'+v.version_number+'">Restaurar</button></article>').join(''):'<p class="empty">Todavía no hay versiones anteriores.</p>'}catch(e){$('#history-status').textContent=e.message}}
$('#show-history').addEventListener('click',async()=>{$('#translation-history').classList.toggle('hidden');if(!$('#translation-history').classList.contains('hidden'))await loadHistory()});
$('#history-list').addEventListener('click',async e=>{const button=e.target.closest('[data-restore]');if(!button)return;if(translationDirty&&!confirm('Hay cambios sin guardar. ¿Descartarlos y restaurar la versión elegida?'))return;if(!confirm('¿Restaurar esta versión? La traducción actual guardada se conservará en el historial.'))return;const c=chapters[chapterPos];$('#history-status').textContent='Restaurando…';try{const result=await api('/api/chapters/'+c.id+'/translation/restore/'+button.dataset.restore,{method:'POST'});$('#translation').value=result.translated_text;c.translated_text=result.translated_text;translationDirty=false;$('#save-status').textContent='Versión restaurada.';$('#history-status').textContent='La versión se restauró y el texto anterior quedó guardado.';await loadHistory()}catch(err){$('#history-status').textContent='Error: '+err.message}});
$('#translation').addEventListener('input',()=>{translationDirty=true;$('#save-status').textContent='Cambios sin guardar';});
window.addEventListener('beforeunload',e=>{if(translationDirty){e.preventDefault();e.returnValue=''}});
function resetGlossaryForm(){editingGlossaryId=null;$('#glossary-form').reset();$('#glossary-submit').textContent='Guardar término';$('#glossary-cancel').classList.add('hidden')}
async function loadGlossary(){if(!currentBook)return;try{const entries=await api('/api/books/'+currentBook.id+'/glossary');$('#glossary-list').innerHTML=entries.length?'<div>'+entries.map(g=>'<article class="book"><div class="bookinfo"><strong>'+esc(g.source_term)+' → '+esc(g.preferred_term)+'</strong><div class="sub small">'+esc(g.rule)+' · '+(g.approved?'Aprobado':'Pendiente')+(g.notes?' · '+esc(g.notes):'')+'</div></div>'+(g.book_id===null?'':'<div class="reader-actions"><button class="secondary" type="button" data-edit-glossary="'+esc(g.id)+'">Editar</button><button class="quiet" type="button" data-delete-glossary="'+esc(g.id)+'">Eliminar</button></div>')+'</article>').join('')+'</div>':'<p class="empty">Todavía no hay términos definidos para esta novela.</p>'}catch(e){$('#glossary-status').textContent=e.message}}
$('#toggle-glossary').addEventListener('click',async()=>{$('#glossary-panel').classList.remove('hidden');await loadGlossary();$('#glossary-source').focus()});
$('#close-glossary').addEventListener('click',()=>$('#glossary-panel').classList.add('hidden'));
$('#glossary-cancel').addEventListener('click',resetGlossaryForm);
$('#glossary-list').addEventListener('click',async e=>{const edit=e.target.closest('[data-edit-glossary]');const remove=e.target.closest('[data-delete-glossary]');if(edit){const entries=await api('/api/books/'+currentBook.id+'/glossary');const entry=entries.find(g=>g.id===edit.dataset.editGlossary);if(!entry)return;editingGlossaryId=entry.id;$('#glossary-source').value=entry.source_term;$('#glossary-target').value=entry.preferred_term;$('#glossary-rule').value=entry.rule;$('#glossary-notes').value=entry.notes||'';$('#glossary-approved').checked=Boolean(entry.approved);$('#glossary-submit').textContent='Guardar cambios';$('#glossary-cancel').classList.remove('hidden');$('#glossary-source').focus();return}if(remove){if(!confirm('¿Eliminar este término del glosario de esta novela?'))return;try{await api('/api/books/'+currentBook.id+'/glossary/'+remove.dataset.deleteGlossary,{method:'DELETE'});if(editingGlossaryId===remove.dataset.deleteGlossary)resetGlossaryForm();$('#glossary-status').textContent='Término eliminado.';await loadGlossary()}catch(err){$('#glossary-status').textContent='Error: '+err.message}}});
$('#glossary-form').addEventListener('submit',async e=>{e.preventDefault();if(!currentBook)return;$('#glossary-status').textContent=editingGlossaryId?'Guardando cambios…':'Guardando término…';const payload={source_term:$('#glossary-source').value.trim(),preferred_term:$('#glossary-target').value.trim(),rule:$('#glossary-rule').value,notes:$('#glossary-notes').value.trim(),approved:$('#glossary-approved').checked};try{await api('/api/books/'+currentBook.id+'/glossary'+(editingGlossaryId?'/'+editingGlossaryId:''),{method:editingGlossaryId?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});$('#glossary-status').textContent=editingGlossaryId?'Cambios guardados.':'Término guardado.';resetGlossaryForm();await loadGlossary()}catch(e){$('#glossary-status').textContent='Error: '+e.message}});
$('#font-size').addEventListener('change',e=>{const size=Number(e.target.value);$('#original').style.fontSize=size+'px';$('#translation').style.fontSize=size+'px'});
$('#back').addEventListener('click',async()=>{if(translationDirty&&!confirm('Hay cambios de traducción sin guardar. ¿Salir sin guardarlos?'))return;try{await persistProgressNow()}catch(e){$('#save-status').textContent='No se pudo guardar el progreso: '+e.message;return}translationDirty=false;$('#reader').style.display='none';$('#library').classList.remove('hidden');await refresh()});

/* Manual narrative-assistance micro-window: no network calls or provider-session automation. */
(function installNarrativeAssistant() {
  if (document.getElementById('narrative-assistant-open')) return;
  const button = document.createElement('button');
  button.id = 'narrative-assistant-open';
  button.type = 'button';
  button.textContent = 'Asistencia narrativa';
  button.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9000;padding:11px 15px;border:1px solid #94a3b8;border-radius:999px;background:#24354b;color:#fff;box-shadow:0 4px 18px #0004;cursor:pointer';
  document.body.appendChild(button);
  const overlay = document.createElement('section');
  overlay.id = 'narrative-assistant-dialog';
  overlay.setAttribute('role','dialog'); overlay.setAttribute('aria-modal','true'); overlay.setAttribute('aria-labelledby','narrative-assistant-title');
  overlay.style.cssText = 'display:none;position:fixed;inset:0;z-index:9001;background:#0b1220c9;padding:18px;align-items:center;justify-content:center';
  overlay.innerHTML = '<div style="width:min(760px,100%);max-height:92vh;overflow:auto;background:#fff;color:#182333;border-radius:14px;padding:22px;box-shadow:0 20px 70px #0008;font:14px/1.5 system-ui,sans-serif"><h2 id="narrative-assistant-title" style="margin-top:0">Microventana de asistencia narrativa</h2><p>NovelTrad prepara el prompt localmente. No envía texto, no lee sesiones web y no automatiza ChatGPT/Gemini. El contenido solo sale si lo autorizás, lo copiás y lo pegás manualmente.</p><label for="na-task-nt" style="display:block;margin:12px 0 5px">Tarea</label><select id="na-task-nt" style="width:100%;padding:9px"><option value="translate">Proponer traducción al español</option><option value="context">Analizar contexto, personajes y relaciones</option><option value="continuity">Revisar continuidad sin inventar canon</option><option value="style">Revisar estilo y claridad</option><option value="terms">Extraer términos candidatos para el glosario</option></select><label for="na-context-nt" style="display:block;margin:12px 0 5px">Contexto opcional</label><textarea id="na-context-nt" rows="3" style="box-sizing:border-box;width:100%;padding:9px" placeholder="Glosario, nombres, época, reglas o instrucciones"></textarea><label for="na-source-nt" style="display:block;margin:12px 0 5px">Fragmento a compartir</label><textarea id="na-source-nt" rows="8" style="box-sizing:border-box;width:100%;padding:9px" placeholder="Pegá solo el fragmento que quieras compartir. Si hay una selección de texto, se copia únicamente dentro de esta ventana."></textarea><label style="display:flex;gap:9px;align-items:flex-start;margin:12px 0"><input id="na-consent-nt" type="checkbox" style="margin-top:4px"><span>Revisé el fragmento y autorizo copiar este contenido al portapapeles para pegarlo manualmente en un servicio externo. Entiendo que al pegarlo allí sale de NovelTrad.</span></label><p style="color:#4b5563">El texto no se guarda en el proyecto ni se envía automáticamente. No se garantiza uso gratuito o ilimitado de cuentas externas. Revisá toda respuesta antes de modificar la traducción.</p><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:14px"><button id="na-copy-nt" type="button" disabled>Copiar prompt autorizado</button><button id="na-chatgpt-nt" type="button" disabled>Abrir ChatGPT</button><button id="na-gemini-nt" type="button" disabled>Abrir Gemini</button><button id="na-close-nt" type="button">Cerrar</button></div><p id="na-status-nt" role="status" aria-live="polite"></p></div>';
  document.body.appendChild(overlay);
  const $ = id => overlay.querySelector('#' + id);
  const task = $('na-task-nt'), context = $('na-context-nt'), source = $('na-source-nt'), consent = $('na-consent-nt');
  const copy = $('na-copy-nt'), chatgpt = $('na-chatgpt-nt'), gemini = $('na-gemini-nt'), status = $('na-status-nt');
  const taskLabels = {
    translate: 'Proponer una traducción al español natural y fiel; conservar nombres propios y no añadir hechos.',
    context: 'Analizar el contexto y separar hechos explícitos, inferencias y dudas; identificar personajes y relaciones sin inventar datos.',
    continuity: 'Revisar continuidad; listar evidencia textual, contradicciones posibles y preguntas abiertas. No convertir hipótesis en canon.',
    style: 'Revisar claridad, ritmo y estilo sin alterar hechos, voz ni intención narrativa.',
    terms: 'Extraer términos candidatos en tabla con original, propuesta, contexto y confianza. No aprobar términos automáticamente.'
  };
  function sync() {
    const enabled = consent.checked && Boolean(source.value.trim());
    copy.disabled = chatgpt.disabled = gemini.disabled = !enabled;
    status.textContent = !consent.checked ? 'Revisá el texto y marcá la autorización explícita.' : !source.value.trim() ? 'Agregá el fragmento que querés compartir.' : 'Autorización activa para copiar. No hay envío automático.';
  }
  function promptText() {
    return ['Actuá como asistente editorial de novelas. No afirmes que verificaste fuentes que no recibiste.',
      'TAREA: ' + taskLabels[task.value],
      'REGLAS: separá hechos, inferencias y desconocidos; no inventes canon; señalá incertidumbres y conservá nombres y sentido.',
      context.value.trim() ? 'CONTEXTO DEL AUTOR:\n' + context.value.trim() : '',
      'FRAGMENTO DEL AUTOR:\n' + source.value.trim(),
      'ENTREGA: respuesta estructurada y verificable. Las propuestas no son cambios aplicados.'
    ].filter(Boolean).join('\n\n');
  }
  button.addEventListener('click', () => {
    const selection = window.getSelection ? String(window.getSelection()).trim() : '';
    if (selection && !source.value.trim()) source.value = selection;
    overlay.style.display = 'flex'; status.textContent = 'Nada se ha compartido todavía.'; sync(); task.focus();
  });
  $('na-close-nt').addEventListener('click', () => { overlay.style.display = 'none'; consent.checked = false; sync(); });
  overlay.addEventListener('click', e => { if (e.target === overlay) { overlay.style.display = 'none'; consent.checked = false; sync(); } });
  consent.addEventListener('change', sync); source.addEventListener('input', sync);
  copy.addEventListener('click', async () => {
    if (!consent.checked || !source.value.trim()) return;
    const value = promptText();
    try { await navigator.clipboard.writeText(value); status.textContent = 'Prompt copiado. Pegalo manualmente en el servicio que elijas.'; }
    catch (_) {
      const temp = document.createElement('textarea'); temp.value = value; temp.setAttribute('readonly',''); temp.style.position = 'fixed'; temp.style.opacity = '0'; document.body.appendChild(temp); temp.select();
      const ok = document.execCommand('copy'); temp.remove();
      status.textContent = ok ? 'Prompt copiado. Pegalo manualmente en el servicio que elijas.' : 'No se pudo copiar. Revisá los permisos del navegador.';
    }
  });
  function openProvider(url) {
    if (!consent.checked || !source.value.trim()) return;
    window.open(url, '_blank', 'noopener,noreferrer');
    status.textContent = 'Se solicitó abrir el servicio en otra pestaña. Si todavía no copiaste el prompt, volvé aquí y usá Copiar prompt autorizado. Pegá y enviá manualmente; NovelTrad no transmite datos.';
  }
  chatgpt.addEventListener('click', () => openProvider('https://chatgpt.com/'));
  gemini.addEventListener('click', () => openProvider('https://gemini.google.com/app'));
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && overlay.style.display === 'flex') { overlay.style.display = 'none'; consent.checked = false; sync(); } });
})();
</script></body></html>'''


def run() -> None:
    import uvicorn
    uvicorn.run("noveltrad.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
