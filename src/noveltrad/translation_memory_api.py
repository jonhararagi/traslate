"""Local FastAPI endpoints for importing and previewing translation-memory packs.

Entries are always imported as drafts regardless of the pack's claimed status.
Approving memory is an explicit local action. No endpoint in this module writes
text to a chapter's saved translation.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import File, HTTPException, UploadFile
from pydantic import BaseModel

from noveltrad.translation_memory import (
    MAX_TRANSLATION_MEMORY_UPLOAD_BYTES,
    TranslationMemoryPackError,
    choose_complete_memory_match,
    parse_translation_memory_pack,
)


class TranslationMemoryPreviewInput(BaseModel):
    source_text: str
    chapter_ref: str | None = None
    include_draft: bool = False


def install_translation_memory_routes(app, data_dir: Callable[[], Path | str]) -> None:
    """Register local-only translation-memory endpoints on the NovelTrad app."""

    def connect_memory_db() -> sqlite3.Connection:
        root = Path(data_dir())
        root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(root / "translation_memory.sqlite3"))
        connection.row_factory = sqlite3.Row
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS translation_memory_entries (
                id TEXT NOT NULL,
                book_id TEXT NOT NULL,
                chapter_ref TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                source_text TEXT NOT NULL,
                target_text TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('draft', 'confirmed', 'rejected')),
                review_status TEXT NOT NULL,
                source_blob_sha TEXT NOT NULL DEFAULT '',
                translation_blob_sha TEXT NOT NULL DEFAULT '',
                imported_at TEXT NOT NULL,
                PRIMARY KEY (book_id, id),
                UNIQUE (book_id, chapter_ref, page_index, source_hash)
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_translation_memory_lookup
            ON translation_memory_entries(book_id, chapter_ref, page_index, status)
            """
        )
        connection.commit()
        return connection

    @app.post("/api/books/{book_id}/translation-memory/import")
    async def import_translation_memory(
        book_id: str,
        file: UploadFile = File(...),
    ):
        """Import a JSONL pack to local memory; never apply it to a chapter."""
        if not book_id.strip() or len(book_id) > 200:
            raise HTTPException(status_code=400, detail="Identificador de libro inválido.")
        filename = (file.filename or "").lower()
        if not filename.endswith((".jsonl", ".ndjson")):
            raise HTTPException(status_code=415, detail="Sube un archivo .jsonl o .ndjson.")
        raw = await file.read(MAX_TRANSLATION_MEMORY_UPLOAD_BYTES + 1)
        await file.close()
        try:
            entries = parse_translation_memory_pack(raw)
        except TranslationMemoryPackError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        inserted = 0
        skipped = 0
        imported_at = datetime.now(timezone.utc).isoformat()
        with connect_memory_db() as connection:
            for entry in entries:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO translation_memory_entries
                    (id, book_id, chapter_ref, page_index, source_hash, source_text,
                     target_text, status, review_status, source_blob_sha,
                     translation_blob_sha, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 'imported_pending_review', ?, ?, ?)
                    """,
                    (
                        entry["id"],
                        book_id,
                        entry["chapter_ref"],
                        entry["page_index"],
                        entry["source_hash"],
                        entry["source_text"],
                        entry["target_text"],
                        entry["source_blob_sha"],
                        entry["translation_blob_sha"],
                        imported_at,
                    ),
                )
                if cursor.rowcount:
                    inserted += 1
                else:
                    skipped += 1
        return {
            "book_id": book_id,
            "total_records": len(entries),
            "imported": inserted,
            "skipped_existing": skipped,
            "imported_status": "draft",
            "explicit_approval_required": True,
            "applied_to_chapters": False,
            "preview_only": True,
        }

    @app.get("/api/books/{book_id}/translation-memory")
    def list_translation_memory(book_id: str, limit: int = 1000):
        """List local memory metadata without returning copyrighted chapter text."""
        if limit < 1 or limit > 5000:
            raise HTTPException(status_code=422, detail="limit debe estar entre 1 y 5000.")
        with connect_memory_db() as connection:
            rows = connection.execute(
                """
                SELECT id, chapter_ref, page_index, status, review_status,
                       length(source_text) AS source_chars,
                       length(target_text) AS target_chars, source_blob_sha,
                       translation_blob_sha, imported_at
                FROM translation_memory_entries
                WHERE book_id = ?
                ORDER BY chapter_ref, page_index
                LIMIT ?
                """,
                (book_id, limit),
            ).fetchall()
        return {"book_id": book_id, "count": len(rows), "entries": [dict(row) for row in rows]}

    @app.post("/api/books/{book_id}/translation-memory/{entry_id}/approve")
    def approve_translation_memory_entry(book_id: str, entry_id: str):
        """Explicitly approve one memory page; approval still does not write a chapter."""
        with connect_memory_db() as connection:
            cursor = connection.execute(
                """
                UPDATE translation_memory_entries
                SET status = 'confirmed', review_status = 'approved_by_user',
                    imported_at = ?
                WHERE book_id = ? AND id = ? AND status != 'rejected'
                """,
                (datetime.now(timezone.utc).isoformat(), book_id, entry_id),
            )
            if not cursor.rowcount:
                raise HTTPException(status_code=404, detail="Entrada de memoria no encontrada o rechazada.")
        return {
            "book_id": book_id,
            "entry_id": entry_id,
            "status": "confirmed",
            "applied_to_chapters": False,
            "preview_only": True,
        }

    @app.post("/api/books/{book_id}/translation-memory/preview")
    def preview_translation_memory(book_id: str, payload: TranslationMemoryPreviewInput):
        """Return a full exact-source match for review; partial pages never form a translation."""
        if not payload.source_text.strip():
            raise HTTPException(status_code=422, detail="source_text no puede estar vacío.")
        if len(payload.source_text) > 2_000_000:
            raise HTTPException(status_code=413, detail="El texto de origen supera el límite de 2 MiB.")
        if payload.chapter_ref is not None and len(payload.chapter_ref) > 200:
            raise HTTPException(status_code=422, detail="chapter_ref es demasiado largo.")

        with connect_memory_db() as connection:
            rows = connection.execute(
                """
                SELECT id, chapter_ref, page_index, source_hash, source_text, target_text,
                       status, review_status, source_blob_sha, translation_blob_sha
                FROM translation_memory_entries
                WHERE book_id = ?
                ORDER BY chapter_ref, page_index
                """,
                (book_id,),
            ).fetchall()
        match = choose_complete_memory_match(
            payload.source_text,
            [dict(row) for row in rows],
            memory_chapter_ref=payload.chapter_ref,
            include_draft=payload.include_draft,
        )
        if not match:
            return {
                "book_id": book_id,
                "matched": False,
                "complete": False,
                "coverage": 0.0,
                "proposed_text": None,
                "preview_only": True,
                "saved": False,
                "auto_applied": False,
                "reason": "No hay una coincidencia exacta con cobertura completa en la memoria autorizada para esta consulta.",
            }
        return {
            "book_id": book_id,
            "matched": True,
            "complete": True,
            "coverage": 1.0,
            "chapter_ref": match["chapter_ref"],
            "page_count": match["page_count"],
            "memory_status": match["status"],
            "proposed_text": match["proposed_text"],
            "preview_only": True,
            "saved": False,
            "auto_applied": False,
            "warning": "Es una sugerencia de memoria, no una traducción validada. Revisa el original antes de usarla.",
        }
