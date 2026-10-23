"""Local, page-aligned translation-memory pack utilities.

This module deliberately stores and previews memory only. It never writes a
translation into a chapter, and imported records are candidates until an
explicit user review promotes them.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

MAX_TRANSLATION_MEMORY_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TRANSLATION_MEMORY_ENTRIES = 50_000
MAX_MEMORY_TEXT_CHARS = 100_000
_ALLOWED_STATUSES = {"draft", "confirmed", "rejected"}
_REQUIRED_FIELDS = {"id", "chapter_id", "page_index", "source_text", "target_text"}


class TranslationMemoryPackError(ValueError):
    """Raised when a translation-memory pack fails schema or size checks."""


def normalize_memory_text(value: str) -> str:
    """Normalize whitespace and case for exact-content matching, not semantics."""
    return re.sub(r"\s+", " ", value.replace("\ufeff", "")).strip().casefold()


def memory_source_hash(value: str) -> str:
    """Return a stable SHA-256 for normalized source text."""
    normalized = normalize_memory_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def parse_translation_memory_pack(raw: bytes) -> list[dict[str, Any]]:
    """Validate JSONL page-alignment records without rewriting source/target text."""
    if not raw:
        raise TranslationMemoryPackError("El archivo JSONL está vacío.")
    if len(raw) > MAX_TRANSLATION_MEMORY_UPLOAD_BYTES:
        raise TranslationMemoryPackError("El archivo supera el límite de 25 MiB.")
    try:
        decoded = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise TranslationMemoryPackError("El archivo debe estar codificado en UTF-8.") from exc

    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_no, line in enumerate(decoded.splitlines(), start=1):
        if not line.strip():
            continue
        if len(records) >= MAX_TRANSLATION_MEMORY_ENTRIES:
            raise TranslationMemoryPackError("El archivo contiene demasiadas entradas.")
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TranslationMemoryPackError(
                f"La línea {line_no} no contiene JSON válido."
            ) from exc
        if not isinstance(item, dict):
            raise TranslationMemoryPackError(f"La línea {line_no} debe ser un objeto JSON.")
        missing = sorted(_REQUIRED_FIELDS - item.keys())
        if missing:
            raise TranslationMemoryPackError(
                f"La línea {line_no} no contiene los campos requeridos: {', '.join(missing)}."
            )

        entry_id = item.get("id")
        chapter_id = item.get("chapter_id")
        page_index = item.get("page_index")
        source_text = item.get("source_text")
        target_text = item.get("target_text")
        status = item.get("status", "draft")
        if not isinstance(entry_id, str) or not entry_id.strip() or len(entry_id) > 200:
            raise TranslationMemoryPackError(f"ID inválido en la línea {line_no}.")
        entry_id = entry_id.strip()
        if entry_id in seen_ids:
            raise TranslationMemoryPackError(f"ID duplicado en la línea {line_no}: {entry_id}.")
        if not isinstance(chapter_id, str) or not chapter_id.strip() or len(chapter_id) > 200:
            raise TranslationMemoryPackError(f"chapter_id inválido en la línea {line_no}.")
        if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 1:
            raise TranslationMemoryPackError(f"page_index debe ser un entero positivo en la línea {line_no}.")
        if not isinstance(source_text, str) or not source_text.strip():
            raise TranslationMemoryPackError(f"source_text está vacío en la línea {line_no}.")
        if not isinstance(target_text, str) or not target_text.strip():
            raise TranslationMemoryPackError(f"target_text está vacío en la línea {line_no}.")
        if len(source_text) > MAX_MEMORY_TEXT_CHARS or len(target_text) > MAX_MEMORY_TEXT_CHARS:
            raise TranslationMemoryPackError(f"Texto demasiado largo en la línea {line_no}.")
        if not isinstance(status, str) or status not in _ALLOWED_STATUSES:
            raise TranslationMemoryPackError(
                f"Estado no admitido en la línea {line_no}; use draft, confirmed o rejected."
            )

        seen_ids.add(entry_id)
        records.append({
            "id": entry_id,
            "chapter_ref": chapter_id.strip(),
            "page_index": page_index,
            "source_text": source_text,
            "target_text": target_text,
            "source_hash": memory_source_hash(source_text),
            # Never trust an imported pack to grant approval. The API downgrades
            # every entry to draft and requires explicit local approval.
            "status": "draft",
            "review_status": "imported_pending_review",
            "source_blob_sha": str(item.get("source_blob_sha", ""))[:100],
            "translation_blob_sha": str(item.get("translation_blob_sha", ""))[:100],
        })
    if not records:
        raise TranslationMemoryPackError("No hay registros JSONL válidos para importar.")
    return records


def choose_complete_memory_match(
    original_text: str,
    entries: list[dict[str, Any]],
    memory_chapter_ref: str | None = None,
    include_draft: bool = False,
) -> dict[str, Any] | None:
    """Find a complete chapter match; never return a partial/mixed-language draft."""
    normalized_original = normalize_memory_text(original_text)
    if not normalized_original:
        return None
    allowed = {"confirmed"}
    if include_draft:
        allowed.add("draft")

    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry.get("status") not in allowed:
            continue
        chapter_ref = str(entry.get("chapter_ref", ""))
        if memory_chapter_ref and chapter_ref != memory_chapter_ref:
            continue
        groups.setdefault(chapter_ref, []).append(entry)

    matches: list[dict[str, Any]] = []
    for chapter_ref, group in groups.items():
        group.sort(key=lambda item: int(item["page_index"]))
        page_numbers = [int(item["page_index"]) for item in group]
        if page_numbers != list(range(1, len(group) + 1)):
            continue
        joined_source = "\f".join(str(item["source_text"]) for item in group)
        if normalize_memory_text(joined_source) != normalized_original:
            continue
        matches.append({
            "chapter_ref": chapter_ref,
            "page_count": len(group),
            "status": "confirmed" if all(item.get("status") == "confirmed" for item in group) else "draft",
            "proposed_text": "\f".join(str(item["target_text"]) for item in group),
            "source_hash": memory_source_hash(joined_source),
        })

    if len(matches) != 1:
        return None
    return matches[0]
