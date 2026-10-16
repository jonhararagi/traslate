"""Stable, deterministic reader-page boundaries shared by the API and tests.

Pages are virtual slices of immutable chapter source text. Their IDs are derived
from the exact source slice, not the reader zoom or current viewport.
"""
from __future__ import annotations

from hashlib import sha256


DEFAULT_READER_PAGE_CHARS = 2400


def split_reader_pages(text: str, max_chars: int = DEFAULT_READER_PAGE_CHARS) -> list[str]:
    """Split text reproducibly, preferring paragraph/line/word boundaries.

    Every source character is retained exactly once. The delimiter belongs to
    the page before the boundary so concatenating the returned pages recreates
    the original byte-for-byte at the Unicode string level.
    """
    if not isinstance(text, str):
        raise TypeError("El texto de lectura debe ser una cadena.")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
        raise ValueError("max_chars debe ser un entero positivo.")
    if not text:
        return [""]
    pages: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        if end < length:
            search_start = start + max(1, max_chars // 2)
            for separator in ("\r\n\r\n", "\n\n", "\r\n", "\n", " ", "\t"):
                boundary = text.rfind(separator, search_start, end)
                if boundary >= search_start:
                    end = boundary + len(separator)
                    break
        if end <= start:
            end = min(start + max_chars, length)
        pages.append(text[start:end])
        start = end
    return pages


def split_text_to_count(text: str, count: int) -> list[str]:
    """Partition a legacy whole-chapter translation into exactly count slices.

    Existing chapter-level translations predate page navigation. This function
    gives them a deterministic initial page view without dropping or rewriting
    any text. Saved page translations subsequently use their source-page hashes.
    """
    if not isinstance(text, str):
        raise TypeError("El texto de traducción debe ser una cadena.")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise ValueError("count debe ser un entero positivo.")
    if not text:
        return [""] * count
    if count == 1:
        return [text]

    pieces: list[str] = []
    start = 0
    length = len(text)
    for index in range(count - 1):
        target = round(length * (index + 1) / count)
        remaining_parts = count - index
        average = max(1, round((length - start) / remaining_parts))
        low = max(start + 1, target - max(1, average // 2))
        high = min(length, target + max(1, average // 2))
        end = target
        found = False
        for separator in ("\r\n\r\n", "\n\n", "\r\n", "\n", " ", "\t"):
            candidates: list[int] = []
            search_from = max(start, low - len(separator))
            while True:
                at = text.find(separator, search_from, high)
                if at < 0:
                    break
                cut = at + len(separator)
                if low <= cut <= high:
                    candidates.append(cut)
                search_from = at + 1
            if candidates:
                end = min(candidates, key=lambda cut: abs(cut - target))
                found = True
                break
        if not found:
            end = max(start, min(length, target))
        if length - start >= remaining_parts and end <= start:
            end = min(length, start + 1)
        pieces.append(text[start:end])
        start = end
    pieces.append(text[start:])
    # When there are more requested pages than characters, zero-length slices
    # are valid; the loop still returns exactly count items.
    if len(pieces) != count or "".join(pieces) != text:
        raise AssertionError("La segmentación no preservó exactamente el texto.")
    return pieces


def page_source_hash(text: str) -> str:
    """Return the stable content identity for a page's original text."""
    if not isinstance(text, str):
        raise TypeError("El texto de página debe ser una cadena.")
    return sha256(text.encode("utf-8")).hexdigest()
