"""Deterministic, offline prose rules for NovelTrad.

This module deliberately does not claim to translate arbitrary prose. It applies
only author-approved phrase mappings, glossary rules, and conservative typography
normalization. No network, model, or persistence is used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable, Mapping


@dataclass(frozen=True)
class StyleProfile:
    id: str
    name: str
    language: str
    description: str
    rules: tuple[str, ...]
    dialogue_open: str = "—"
    ellipsis: str = "…"
    preserve_paragraphs: bool = True


PROFILES: dict[str, StyleProfile] = {
    "light_novel_es": StyleProfile(
        id="light_novel_es",
        name="Novela ligera en español",
        language="es",
        description="Prosa ágil, lectura clara y diálogos diferenciados; perfil genérico configurable.",
        rules=(
            "Conservar el orden de los hechos y la intención del narrador.",
            "Mantener los párrafos y los cambios de escena del original.",
            "Usar raya de diálogo cuando el proyecto la haya elegido como convención.",
            "No convertir pensamientos, honoríficos ni nombres propios sin una regla aprobada.",
            "No añadir explicaciones, emociones ni información que no aparezcan en el original.",
        ),
    ),
    "faithful_literary_es": StyleProfile(
        id="faithful_literary_es",
        name="Traducción literaria fiel",
        language="es",
        description="Prioriza significado, voz narrativa y matices antes que la literalidad mecánica.",
        rules=(
            "Preservar focalización, tiempo verbal y distancia narrativa.",
            "Evitar omisiones y añadidos; marcar ambigüedades en lugar de resolverlas inventando.",
            "Conservar imágenes y figuras retóricas salvo que exista una regla editorial aprobada.",
            "No homogeneizar las voces de personajes diferentes.",
        ),
    ),
    "webnovel_es": StyleProfile(
        id="webnovel_es",
        name="Novela web en español",
        language="es",
        description="Perfil de lectura serial: consistencia entre capítulos y terminología estable.",
        rules=(
            "Mantener títulos, separadores, notas y cortes de capítulo.",
            "Reutilizar las traducciones aprobadas del glosario sin variaciones accidentales.",
            "No adelantar revelaciones ni reinterpretar referencias de capítulos posteriores.",
            "Conservar repeticiones deliberadas y el ritmo de lectura serial.",
        ),
    ),
}


@dataclass(frozen=True)
class TermRule:
    source: str
    target: str
    mode: str = "translate"  # translate, preserve, protect
    approved: bool = True

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("El término de origen no puede estar vacío.")
        if self.mode not in {"translate", "preserve", "protect", "contextual"}:
            raise ValueError("mode debe ser translate, preserve o protect.")
        if self.mode == "translate" and not self.target.strip():
            raise ValueError("Una regla translate necesita un término de destino.")


@dataclass(frozen=True)
class EditReport:
    text: str
    replacements: tuple[tuple[str, str, int], ...]
    warnings: tuple[str, ...]
    profile_id: str


def get_profile(profile_id: str) -> StyleProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Perfil de prosa desconocido: {profile_id}") from exc


def _case_like(source: str, replacement: str) -> str:
    if source.isupper():
        return replacement.upper()
    if source.istitle():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _replace_literal(text: str, source: str, target: str) -> tuple[str, int]:
    # Unicode word boundaries prevent replacing a term inside a longer word.
    pattern = re.compile(r"(?<!\w)" + re.escape(source) + r"(?!\w)", re.IGNORECASE)
    count = 0

    def substitute(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return _case_like(match.group(0), target)

    return pattern.sub(substitute, text), count


def apply_offline_rules(
    text: str,
    *,
    profile_id: str = "light_novel_es",
    term_rules: Iterable[TermRule] = (),
    phrase_map: Mapping[str, str] | None = None,
    normalize_typography: bool = True,
) -> EditReport:
    """Apply explicit deterministic rules; never infer a translation."""
    if not isinstance(text, str):
        raise TypeError("text debe ser una cadena.")
    profile = get_profile(profile_id)
    result = text.replace("\r\n", "\n").replace("\r", "\n")
    applied: list[tuple[str, str, int]] = []
    warnings: list[str] = []

    # Approved contextual terms are protected from global replacement. We report
    # their occurrences for review instead of pretending a word has one meaning.
    protected: dict[str, str] = {}
    rules = [rule for rule in term_rules if rule.approved]
    rules.sort(key=lambda rule: len(rule.source), reverse=True)
    for index, rule in enumerate(rules):
        if rule.mode == "contextual":
            pattern = re.compile(r"(?<!\w)" + re.escape(rule.source) + r"(?!\w)", re.IGNORECASE)
            count = len(pattern.findall(result))
            if count:
                warnings.append(
                    f"El término contextual «{rule.source}» aparece {count} vez/veces; no se sustituyó automáticamente. Revisá cada ocurrencia."
                )
        if rule.mode not in {"preserve", "protect", "contextual"}:
            continue
        token = f"\uE000NT{index}TOKEN\uE001"
        result, count = _replace_literal(result, rule.source, token)
        if count:
            protected[token] = rule.source
            if rule.mode in {"preserve", "protect"}:
                applied.append((rule.source, rule.source, count))

    mappings: list[tuple[str, str]] = []
    for rule in rules:
        if rule.mode == "translate":
            mappings.append((rule.source, rule.target))
    mappings.extend((str(k), str(v)) for k, v in (phrase_map or {}).items() if str(k).strip())
    mappings.sort(key=lambda pair: len(pair[0]), reverse=True)
    for source, target in mappings:
        result, count = _replace_literal(result, source, target)
        if count:
            applied.append((source, target, count))

    if normalize_typography:
        result = re.sub(r"[ \t]+(?=\n)", "", result)
        result = re.sub(r"[ \t]+$", "", result, flags=re.MULTILINE)
        result = re.sub(r"(?<!\.)\.{3}(?!\.)", profile.ellipsis, result)
        result = re.sub(r"\n{3,}", "\n\n", result)
        if profile.dialogue_open == "—":
            result = re.sub(r"(?m)^[ \t]*-[ \t]+", "— ", result)

    for token, original in protected.items():
        result = result.replace(token, original)

    if not mappings:
        warnings.append(
            "No hay diccionario de traducción aprobado: el texto no se tradujo; solo se aplicaron reglas de formato."
        )
    elif not any(count for _, _, count in applied):
        warnings.append("Ninguna regla coincidió con el fragmento; no se generó una traducción nueva.")
    warnings.append(
        "Modo determinista sin IA: solo transforma coincidencias explícitas. Revisá manualmente ambigüedades y frases no cubiertas."
    )
    return EditReport(result, tuple(applied), tuple(warnings), profile.id)


def lint_chapter(text: str, *, profile_id: str = "light_novel_es") -> tuple[str, ...]:
    """Return conservative, non-blocking checks; do not rewrite the chapter."""
    get_profile(profile_id)
    warnings: list[str] = []
    if not text.strip():
        return ("El capítulo está vacío.",)
    if "\r" in text:
        warnings.append("Hay finales de línea mixtos o Windows; se pueden normalizar.")
    if re.search(r"(?m)^-[ \t]+", text):
        warnings.append("Hay líneas de diálogo con guion; verificá la convención de diálogo del proyecto.")
    if re.search(r"(?<!\.)\.{3}(?!\.)", text):
        warnings.append("Se encontraron tres puntos; el perfil usa el carácter de elipsis … al normalizar.")
    if re.search(r"(?m)^\s+$", text):
        warnings.append("Hay líneas que contienen solo espacios.")
    return tuple(warnings)
