from noveltrad.linguistic_analysis import (
    NarrativeFact,
    analyze_text,
    check_narrative_facts,
)


def test_token_offsets_round_trip_to_exact_source():
    text = "Oknodie found a rare item. She kept it."
    result = analyze_text(text)
    assert [s.text for s in result.sentences] == ["Oknodie found a rare item.", "She kept it."]
    for sentence in result.sentences:
        for token in sentence.tokens:
            assert text[token.start:token.end] == token.text


def test_alias_matching_prefers_longer_names_and_keeps_offsets():
    text = "Yume Kuro met Kuro."
    result = analyze_text(text, {"yume-kuro": ["Yume Kuro", "Yume"], "kuro": ["Kuro"]})
    assert [(m.entity_id, m.alias) for m in result.entities] == [
        ("yume-kuro", "Yume Kuro"), ("kuro", "Kuro")
    ]
    assert all(text[m.start:m.end] == m.alias for m in result.entities)


def test_unknown_name_and_pronouns_are_marked_as_heuristics():
    result = analyze_text("Anzu said she would return.")
    assert any(t.kind == "proper_noun_candidate" for s in result.sentences for t in s.tokens)
    assert any("pronombres" in warning for warning in result.warnings)


def test_conflicting_confirmed_facts_are_flagged_with_provenance():
    facts = [
        NarrativeFact("Oknodie", "location", "Academy", "chapter-1"),
        NarrativeFact("Oknodie", "location", "Capital", "chapter-8"),
    ]
    findings = check_narrative_facts(facts)
    assert len(findings) == 1
    assert findings[0].kind == "conflict"
    assert findings[0].status == "needs_review"
    assert findings[0].sources == ("chapter-1", "chapter-8")


def test_hypothesis_never_becomes_a_confirmed_conflict():
    findings = check_narrative_facts([
        NarrativeFact("Oknodie", "ability", "Steal", "chapter-4"),
        NarrativeFact("Oknodie", "ability", "Copy", "reader-inference", "hypothesis"),
    ])
    assert [f.kind for f in findings] == ["non_canon_evidence"]
    assert findings[0].status == "not_confirmed"


def test_empty_text_and_invalid_fact_are_explicit():
    assert "El texto está vacío." in analyze_text("  ").warnings
    import pytest
    with pytest.raises(ValueError):
        NarrativeFact("Oknodie", "age", "12", "", "confirmed")
