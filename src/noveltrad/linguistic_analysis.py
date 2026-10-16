"""Lightweight, offline linguistic annotation and evidence-aware narrative checks.

This is a conservative rule-based foundation, not a general translator or a
semantic-understanding model. It only reports heuristics and checks facts the
user explicitly supplies with provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class Sentence:
    text: str
    start: int
    end: int
    tokens: tuple[Token, ...]


@dataclass(frozen=True)
class EntityMention:
    entity_id: str
    canonical_name: str
    alias: str
    start: int
    end: int
    sentence_index: int


@dataclass(frozen=True)
class Analysis:
    sentences: tuple[Sentence, ...]
    entities: tuple[EntityMention, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class NarrativeFact:
    """A user-curated fact; the engine never promotes extracted guesses to facts."""
    subject: str
    predicate: str
    value: str
    source: str
    status: str = "confirmed"

    def __post_init__(self) -> None:
        if not all(x.strip() for x in (self.subject, self.predicate, self.value, self.source)):
            raise ValueError("subject, predicate, value y source son obligatorios")
        if self.status not in {"confirmed", "inference", "hypothesis", "disputed"}:
            raise ValueError("status debe ser confirmed, inference, hypothesis o disputed")


@dataclass(frozen=True)
class NarrativeFinding:
    kind: str
    status: str
    message: str
    sources: tuple[str, ...]
    facts: tuple[NarrativeFact, ...]


_WORD_RE = re.compile(r"[^\\W_]+(?:['’][^\\W_]+)*|[^\\w\\s]", re.UNICODE)
_SENTENCE_RE = re.compile(r"[^.!?…]+(?:[.!?…]+[”’\"')\\]]*)?|[.!?…]+")
_PRONOUNS = {
    "he", "she", "they", "him", "her", "them", "his", "hers", "their",
    "it", "its", "i", "we", "you", "me", "us", "my", "our", "your",
    "él", "ella", "ellos", "ellas", "lo", "la", "le", "ellos", "ellas",
}
_COMMON_LOWER = {
    "a", "an", "the", "and", "or", "but", "if", "then", "when", "while",
    "as", "at", "by", "for", "from", "in", "into", "of", "on", "to",
    "with", "without", "is", "was", "were", "be", "been", "being", "has",
    "have", "had", "do", "does", "did", "not", "no", "yes", "she", "he",
    "they", "it", "i", "we", "you", "her", "his", "their", "this", "that",
    "these", "those", "there", "here", "who", "what", "which", "how",
}


def _kind(word: str) -> str:
    if not word:
        return "punctuation"
    if re.fullmatch(r"[^\\w\\s]", word, re.UNICODE):
        return "punctuation"
    if word.isdigit():
        return "number"
    folded = word.casefold()
    if folded in _PRONOUNS:
        return "pronoun"
    if folded in {"a", "an", "the", "this", "that", "these", "those"}:
        return "determiner"
    if folded in {"and", "or", "but", "if", "because", "although", "while", "when"}:
        return "conjunction"
    if folded in {"in", "on", "at", "by", "for", "from", "of", "to", "with", "without", "into", "over", "under"}:
        return "preposition"
    if folded in {"is", "am", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did"}:
        return "auxiliary_or_verb"
    if folded.endswith("ly"):
        return "adverb_heuristic"
    if folded.endswith(("ing", "ed")):
        return "verb_or_participle_heuristic"
    if word[:1].isupper() and folded not in _COMMON_LOWER:
        return "proper_noun_candidate"
    return "word"


def analyze_text(text: str, aliases: Mapping[str, Iterable[str]] | None = None) -> Analysis:
    """Annotate token offsets, sentence spans and explicitly configured aliases.

    Offsets are Python string offsets into the exact input. POS labels are
    deliberately heuristic and must not be treated as a full parser.
    """
    if not isinstance(text, str):
        raise TypeError("text debe ser una cadena")
    sentence_rows: list[Sentence] = []
    for match in _SENTENCE_RE.finditer(text):
        raw = match.group(0)
        left_trim = len(raw) - len(raw.lstrip())
        right = len(raw.rstrip())
        if right <= left_trim:
            continue
        start = match.start() + left_trim
        end = match.start() + right
        sentence_text = text[start:end]
        tokens = tuple(
            Token(m.group(0), start + m.start(), start + m.end(), _kind(m.group(0)))
            for m in _WORD_RE.finditer(sentence_text)
        )
        if tokens:
            sentence_rows.append(Sentence(sentence_text, start, end, tokens))

    mention_rows: list[EntityMention] = []
    warnings: list[str] = []
    if aliases:
        patterns: list[tuple[int, str, str, str, re.Pattern[str]]] = []
        for entity_id, names in aliases.items():
            for name in set(names):
                if name.strip():
                    patterns.append((len(name), entity_id, str(names and name), name,
                                     re.compile(r"(?<!\\w)" + re.escape(name) + r"(?!\\w)", re.IGNORECASE)))
        patterns.sort(key=lambda item: item[0], reverse=True)
        occupied: list[tuple[int, int]] = []
        for _, entity_id, canonical, alias, pattern in patterns:
            for match in pattern.finditer(text):
                if any(match.start() < end and match.end() > start for start, end in occupied):
                    continue
                sentence_index = next(
                    (i for i, sentence in enumerate(sentence_rows)
                     if sentence.start <= match.start() < sentence.end),
                    -1,
                )
                mention_rows.append(EntityMention(
                    entity_id, canonical, alias, match.start(), match.end(), sentence_index
                ))
                occupied.append((match.start(), match.end()))
        mention_rows.sort(key=lambda row: row.start)
        if any(row.sentence_index < 0 for row in mention_rows):
            warnings.append("Hay menciones de entidades fuera de una oración segmentada; revisá la puntuación.")
    if not text.strip():
        warnings.append("El texto está vacío.")
    if re.search(r"(?i)\\b(?:he|she|they|it|él|ella|ellos|ellas)\\b", text):
        warnings.append("Se detectaron pronombres; la resolución de referencias no es automática y requiere contexto.")
    if any(token.kind == "proper_noun_candidate" for sentence in sentence_rows for token in sentence.tokens):
        warnings.append("Los nombres propios son candidatos heurísticos; confirmalos en el glosario.")
    return Analysis(tuple(sentence_rows), tuple(mention_rows), tuple(warnings))


def check_narrative_facts(facts: Iterable[NarrativeFact]) -> tuple[NarrativeFinding, ...]:
    """Find explicit value conflicts for the same subject/predicate.

    Only confirmed facts are compared as hard evidence. Inferences and hypotheses
    are surfaced separately and cannot create a canon conflict on their own.
    """
    grouped: dict[tuple[str, str], list[NarrativeFact]] = {}
    for fact in facts:
        grouped.setdefault((fact.subject.casefold().strip(), fact.predicate.casefold().strip()), []).append(fact)

    findings: list[NarrativeFinding] = []
    for (_, _), group in grouped.items():
        confirmed = [fact for fact in group if fact.status == "confirmed"]
        values: dict[str, list[NarrativeFact]] = {}
        for fact in confirmed:
            values.setdefault(fact.value.casefold().strip(), []).append(fact)
        if len(values) > 1:
            findings.append(NarrativeFinding(
                kind="conflict",
                status="needs_review",
                message=(
                    f"Hay valores confirmados incompatibles para «{confirmed[0].subject}» / "
                    f"«{confirmed[0].predicate}». No se elige uno automáticamente."
                ),
                sources=tuple(dict.fromkeys(fact.source for fact in confirmed)),
                facts=tuple(confirmed),
            ))
        non_confirmed = [fact for fact in group if fact.status != "confirmed"]
        if non_confirmed:
            findings.append(NarrativeFinding(
                kind="non_canon_evidence",
                status="not_confirmed",
                message="Hay inferencias, hipótesis o datos disputados; no se elevan a hechos confirmados.",
                sources=tuple(dict.fromkeys(fact.source for fact in non_confirmed)),
                facts=tuple(non_confirmed),
            ))
    return tuple(findings)
