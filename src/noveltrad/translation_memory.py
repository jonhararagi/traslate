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
_REQUIRED_FIELDS = {"id", "chapter_id", "page_index", "chapter_page_count", "chapter_ends_with_page_separator", "source_text", "target_text"}


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
        chapter_page_count = item.get("chapter_page_count")
        chapter_ends_with_page_separator = item.get("chapter_ends_with_page_separator")
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
        if isinstance(chapter_page_count, bool) or not isinstance(chapter_page_count, int) or chapter_page_count < 1:
            raise TranslationMemoryPackError(f"chapter_page_count debe ser un entero positivo en la línea {line_no}.")
        if page_index > chapter_page_count:
            raise TranslationMemoryPackError(f"page_index supera chapter_page_count en la línea {line_no}.")
        if not isinstance(chapter_ends_with_page_separator, bool):
            raise TranslationMemoryPackError(f"chapter_ends_with_page_separator debe ser booleano en la línea {line_no}.")
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
            "chapter_page_count": chapter_page_count,
            "chapter_ends_with_page_separator": chapter_ends_with_page_separator,
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

    # A pack is importable only when every referenced chapter is complete.
    # This prevents a partial set of pages from masquerading as a whole chapter.
    chapters: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        chapters.setdefault(record["chapter_ref"], []).append(record)
    for chapter_ref, chapter_records in chapters.items():
        page_count = chapter_records[0]["chapter_page_count"]
        terminal_separator = chapter_records[0]["chapter_ends_with_page_separator"]
        page_indices = sorted(record["page_index"] for record in chapter_records)
        if any(
            record["chapter_page_count"] != page_count
            or record["chapter_ends_with_page_separator"] != terminal_separator
            for record in chapter_records
        ):
            raise TranslationMemoryPackError(
                f"Metadatos de páginas incoherentes para el capítulo {chapter_ref}."
            )
        if page_indices != list(range(1, page_count + 1)):
            raise TranslationMemoryPackError(
                f"El capítulo {chapter_ref} está incompleto: se requieren las páginas 1–{page_count}."
            )
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
        page_count = int(group[0].get("chapter_page_count", 0))
        terminal_values = {item.get("chapter_ends_with_page_separator") for item in group}
        if page_count != len(group) or page_numbers != list(range(1, page_count + 1)):
            continue
        if len(terminal_values) != 1 or not isinstance(next(iter(terminal_values)), bool):
            continue
        joined_source = "\f".join(str(item["source_text"]) for item in group)
        if normalize_memory_text(joined_source) != normalized_original:
            continue
        proposed_text = "\f".join(str(item["target_text"]) for item in group)
        if next(iter(terminal_values)):
            proposed_text += "\f"
        matches.append({
            "chapter_ref": chapter_ref,
            "page_count": page_count,
            "status": "confirmed" if all(item.get("status") == "confirmed" for item in group) else "draft",
            "proposed_text": proposed_text,
            "source_hash": memory_source_hash(joined_source),
        })

    if len(matches) != 1:
        return None
    return matches[0]


_RETRIEVAL_STOPWORDS = {
    "a", "about", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "being", "between",
    "both", "but", "by", "can", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his",
    "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of",
    "off", "on", "once", "only", "or", "other", "our", "ours", "ourselves",
    "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "would", "you",
    "your", "yours", "yourself", "yourselves",
}


def _translation_memory_terms(value: str) -> set[str]:
    """Extract lexical hints for low-cost retrieval; this is not semantic search."""
    return {
        token
        for token in re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'-]{1,}", value.casefold())
        if len(token) >= 3 and token not in _RETRIEVAL_STOPWORDS
    }


def retrieve_confirmed_translation_examples(
    source_text: str,
    entries: list[dict[str, Any]],
    *,
    max_examples: int = 2,
    max_context_chars: int = 4200,
    max_example_chars: int = 3600,
    min_shared_terms: int = 2,
) -> list[dict[str, Any]]:
    """Select a few approved page pairs with lexical overlap for a translation prompt.

    Retrieval is intentionally conservative and local: it considers confirmed
    entries only, scores shared non-stopword tokens, excludes an exact source
    page (which is a memory-match concern rather than an example), and bounds
    the total context. It does not claim semantic similarity or approve drafts.
    """
    if not isinstance(source_text, str) or not source_text.strip():
        return []
    if max_examples < 1 or max_context_chars < 1 or max_example_chars < 1:
        return []

    query_terms = _translation_memory_terms(source_text)
    if not query_terms:
        return []
    normalized_source = normalize_memory_text(source_text)
    ranked: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "confirmed":
            continue
        example_source = item.get("source_text")
        example_target = item.get("target_text")
        if (
            not isinstance(example_source, str)
            or not example_source.strip()
            or not isinstance(example_target, str)
            or not example_target.strip()
        ):
            continue
        if normalize_memory_text(example_source) == normalized_source:
            continue
        pair_chars = len(example_source) + len(example_target)
        if pair_chars > max_example_chars:
            continue
        terms = _translation_memory_terms(example_source)
        shared = sorted(query_terms & terms)
        if len(shared) < min_shared_terms:
            continue
        # Normalize overlap by example size so long pages do not win solely
        # because they contain more words; ties remain deterministic.
        score = len(shared) / (len(terms) ** 0.5 if terms else 1.0)
        ranked.append({
            "chapter_ref": str(item.get("chapter_ref") or item.get("chapter_id") or ""),
            "page_index": int(item.get("page_index") or 0),
            "source_text": example_source,
            "target_text": example_target,
            "matched_terms": shared,
            "score": round(score, 6),
            "pair_chars": pair_chars,
        })

    ranked.sort(key=lambda item: (
        -float(item["score"]),
        -len(item["matched_terms"]),
        str(item["chapter_ref"]),
        int(item["page_index"]),
    ))
    selected: list[dict[str, Any]] = []
    total_chars = 0
    for item in ranked:
        # Fixed framing overhead keeps the context limit meaningful.
        framed_chars = int(item["pair_chars"]) + 120
        if total_chars + framed_chars > max_context_chars:
            continue
        selected.append(item)
        total_chars += framed_chars
        if len(selected) >= max_examples:
            break
    return selected
