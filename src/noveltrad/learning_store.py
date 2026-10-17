"""Portable, deduplicated learning records and chapter Markdown exports.

This module deliberately keeps translated prose and reusable translation decisions
in separate directories. It does not infer or approve decisions from raw text.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEARNING_FILES = {
    "names": "nombres-y-personajes.json",
    "terminology": "terminologia-otaku-gamer.json",
    "symbols": "simbolos-y-formato.json",
    "rules": "reglas-de-traduccion.json",
    "ambiguities": "ambiguedades-resueltas.json",
}
VALID_CATEGORIES = frozenset(LEARNING_FILES)
VALID_STATUSES = frozenset({"candidate", "confirmed", "rejected"})


def _normal(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", " ", value).strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_chapter_name(chapter_number: int, title: str = "") -> str:
    if isinstance(chapter_number, bool) or not isinstance(chapter_number, int) or chapter_number < 1:
        raise ValueError("chapter_number must be a positive integer")
    slug = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower()[:60].strip("-")
    suffix = f"-{slug}" if slug else ""
    return f"capitulo-{chapter_number:03d}{suffix}.md"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class TranslationLearningStore:
    """Persist reviewed learning separately from translated chapter text."""

    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir).expanduser().resolve()
        self.translation_dir = self.project_dir / "traduccion"
        self.learning_dir = self.project_dir / "aprendizaje"

    def _load_category(self, category: str) -> dict[str, Any]:
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unknown learning category: {category}")
        path = self.learning_dir / LEARNING_FILES[category]
        if not path.exists():
            return {"schema_version": 1, "category": category, "entries": []}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Learning file is unreadable: {path.name}") from exc
        if (not isinstance(value, dict) or value.get("category") != category
                or not isinstance(value.get("entries"), list)):
            raise ValueError(f"Learning file has an invalid structure: {path.name}")
        return value

    def record_decision(
        self,
        *,
        category: str,
        source: str,
        target: str,
        decision_type: str,
        context: str,
        chapter: int,
        evidence: str,
        status: str = "candidate",
        notes: str = "",
    ) -> dict[str, Any]:
        """Add a decision or enrich its evidence without duplicating the rule.

        Callers must supply a decision extracted/reviewed by a human or an explicit
        workflow. Repeated narrative actions are not decisions unless represented
        by a distinct source pattern and translation rule.
        """
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Unknown learning category: {category}")
        if status not in VALID_STATUSES:
            raise ValueError(f"Unknown decision status: {status}")
        for name, value in (("source", source), ("target", target),
                            ("decision_type", decision_type), ("context", context),
                            ("evidence", evidence)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if isinstance(chapter, bool) or not isinstance(chapter, int) or chapter < 1:
            raise ValueError("chapter must be a positive integer")

        data = self._load_category(category)
        key = (_normal(source), _normal(target), _normal(decision_type))
        existing = next((entry for entry in data["entries"] if (
            _normal(str(entry.get("source", ""))),
            _normal(str(entry.get("target", ""))),
            _normal(str(entry.get("decision_type", ""))),
        ) == key), None)
        evidence_item = {"chapter": chapter, "context": context.strip(), "excerpt": evidence.strip()}
        if existing is not None:
            prior = existing.setdefault("evidence", [])
            evidence_key = (chapter, _normal(context), _normal(evidence))
            if not any((item.get("chapter"), _normal(str(item.get("context", ""))),
                        _normal(str(item.get("excerpt", "")))) == evidence_key for item in prior):
                prior.append(evidence_item)
            if notes.strip() and notes.strip() not in existing.setdefault("notes", []):
                existing["notes"].append(notes.strip())
            # Rejected rules are immutable; candidates can be explicitly confirmed or rejected.
            if existing.get("status") == "rejected":
                existing["updated_at"] = _now()
                _atomic_json(self.learning_dir / LEARNING_FILES[category], data)
                return {"created": False, "entry": existing, "status": "rejected"}
            if status in {"confirmed", "rejected"}:
                existing["status"] = status
            existing["updated_at"] = _now()
            _atomic_json(self.learning_dir / LEARNING_FILES[category], data)
            return {"created": False, "entry": existing, "status": existing["status"]}

        entry = {
            "id": f"{category}-{len(data['entries']) + 1:05d}",
            "source": source.strip(),
            "target": target.strip(),
            "decision_type": decision_type.strip(),
            "context": context.strip(),
            "status": status,
            "evidence": [evidence_item],
            "notes": [notes.strip()] if notes.strip() else [],
            "created_at": _now(),
            "updated_at": _now(),
        }
        data["entries"].append(entry)
        _atomic_json(self.learning_dir / LEARNING_FILES[category], data)
        return {"created": True, "entry": entry, "status": status}

    def save_chapter(self, chapter_number: int, title: str, translated_text: str) -> Path:
        """Write only translated prose under traduccion/, never learning metadata."""
        if not isinstance(translated_text, str) or not translated_text.strip():
            raise ValueError("translated_text must not be empty")
        filename = _safe_chapter_name(chapter_number, title)
        self.translation_dir.mkdir(parents=True, exist_ok=True)
        destination = self.translation_dir / filename
        if destination.parent != self.translation_dir:
            raise ValueError("Invalid chapter destination")
        heading = f"# Capítulo {chapter_number:03d}"
        if title.strip():
            heading += f" — {title.strip()}"
        content = f"{heading}\n\n{translated_text.rstrip()}\n"
        temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def export_learning_index(self) -> Path:
        """Write a small index for humans; canonical learning stays in JSON files."""
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        lines = ["# Aprendizaje de traducción", "",
                 "Las entradas candidatas no son reglas confirmadas. La prosa traducida está en `../traduccion/`.", ""]
        for category, filename in LEARNING_FILES.items():
            data = self._load_category(category)
            category_path = self.learning_dir / filename
            if not category_path.exists():
                _atomic_json(category_path, data)
            confirmed = sum(1 for entry in data["entries"] if entry.get("status") == "confirmed")
            candidates = sum(1 for entry in data["entries"] if entry.get("status") == "candidate")
            lines.append(f"- **{filename}**: {len(data['entries'])} entradas; {confirmed} confirmadas; {candidates} candidatas.")
        path = self.learning_dir / "README.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
