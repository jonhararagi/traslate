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



def test_equal_length_case_variant_aliases_are_deterministic():
    text = "Kuro arrived."
    aliases = {"kuro-id": ["Kuro", "KURO"]}
    first = analyze_text(text, aliases)
    second = analyze_text(text, aliases)
    assert first.entities == second.entities
    assert len(first.entities) == 1
    mention = first.entities[0]
    assert mention.canonical_name == "Kuro"
    assert text[mention.start:mention.end].casefold() == mention.alias.casefold()


def test_unordered_alias_sets_choose_canonical_name_independent_of_construction_order():
    from itertools import combinations, permutations

    def find_order_sensitive_aliases(collection_type):
        # Alias strings with the same low hash bits force probe collisions in
        # small CPython sets. Pick a trio where construction order changes the
        # observed iteration order, so this test exercises the actual defect.
        candidates = [f"Alias-{index:03d}" for index in range(512)]
        buckets = {}
        for alias in candidates:
            buckets.setdefault(hash(alias) & 7, []).append(alias)

        for bucket in buckets.values():
            for aliases in combinations(bucket, 3):
                orders = tuple(permutations(aliases))
                iteration_orders = {
                    tuple(collection_type(order)) for order in orders
                }
                if len({order[0] for order in iteration_orders}) > 1:
                    return aliases, orders
        raise AssertionError(
            f"Could not find order-sensitive aliases for {collection_type.__name__}"
        )

    for collection_type in (set, frozenset):
        aliases, construction_orders = find_order_sensitive_aliases(collection_type)
        expected_canonical = min(aliases, key=lambda value: (value.casefold(), value))
        observed_canonicals = []

        # The same values are inserted in every possible order. At least two
        # constructions have different iteration-first values; none may affect
        # the selected canonical name.
        for order in construction_orders:
            names = collection_type(order)
            result = analyze_text(aliases[0], {"entity-id": names})
            assert len(result.entities) == 1
            observed_canonicals.append(result.entities[0].canonical_name)

        assert observed_canonicals == [expected_canonical] * len(construction_orders)


def test_invalid_alias_and_fact_inputs_fail_explicitly():
    import pytest

    with pytest.raises(TypeError):
        analyze_text("Kuro", {"kuro-id": [None]})
    with pytest.raises(TypeError):
        analyze_text("Kuro", [])
    with pytest.raises(TypeError):
        NarrativeFact("Oknodie", "age", 12, "chapter-1")
    with pytest.raises(TypeError):
        check_narrative_facts([{"subject": "Oknodie"}])
