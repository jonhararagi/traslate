from noveltrad.narrative_rules import (
    PROFILES,
    TermRule,
    apply_offline_rules,
    get_profile,
    lint_chapter,
)


def test_profiles_are_documented_and_available():
    assert {"light_novel_es", "faithful_literary_es", "webnovel_es"} <= set(PROFILES)
    assert all(profile.rules and profile.description for profile in PROFILES.values())
    assert get_profile("webnovel_es").language == "es"


def test_offline_rules_translate_only_explicit_approved_mappings():
    result = apply_offline_rules(
        "The Guild gave the Hero a potion. Unknown phrase.",
        term_rules=[
            TermRule("The Guild", "El Gremio", "translate", True),
            TermRule("Hero", "Héroe", "translate", True),
            TermRule("potion", "poción", "translate", True),
            TermRule("Unknown phrase", "Frase desconocida", "translate", False),
        ],
        normalize_typography=False,
    )
    assert result.text == "El Gremio gave the Héroe a poción. Unknown phrase."
    assert len(result.replacements) == 3
    assert any("sin IA" in warning for warning in result.warnings)


def test_preserve_rule_protects_proper_nouns_from_later_mappings():
    result = apply_offline_rules(
        "Anzu met Anzu's friend.",
        term_rules=[
            TermRule("Anzu", "Anzu", "preserve"),
            TermRule("Anzu's friend", "el amigo de Anzu", "translate"),
        ],
        normalize_typography=False,
    )
    assert result.text == "Anzu met Anzu's friend."


def test_phrase_map_prefers_longer_phrases():
    result = apply_offline_rules(
        "magic stone and stone",
        phrase_map={"magic stone": "piedra mágica", "stone": "piedra"},
        normalize_typography=False,
    )
    assert result.text == "piedra mágica and piedra"


def test_typography_normalization_is_conservative():
    result = apply_offline_rules(" - Hello...  \n\n\nWorld  ", normalize_typography=True)
    assert result.text == "— Hello…\n\nWorld"
    assert lint_chapter(" - Hello...")  # non-blocking diagnostics


def test_unknown_profile_and_invalid_rule_are_rejected():
    import pytest

    with pytest.raises(ValueError, match="desconocido"):
        get_profile("made-up")
    with pytest.raises(ValueError, match="destino"):
        TermRule("hello", "", "translate")


def test_no_dictionary_does_not_claim_to_translate():
    result = apply_offline_rules("A sentence.", normalize_typography=False)
    assert result.text == "A sentence."
    assert any("no se tradujo" in warning for warning in result.warnings)


def test_lint_empty_chapter():
    assert lint_chapter("   ") == ("El capítulo está vacío.",)


def test_contextual_term_is_reported_and_never_globally_replaced():
    result = apply_offline_rules(
        "She farmed monsters, then returned to the farm.",
        term_rules=[TermRule("farm", "farmear", "contextual", True)],
        normalize_typography=False,
    )
    assert result.text == "She farmed monsters, then returned to the farm."
    assert any("término contextual" in warning and "farm" in warning for warning in result.warnings)
    assert not result.replacements


def test_contextual_mode_is_a_valid_glossary_rule():
    rule = TermRule("steal", "robar", "contextual", True)
    assert rule.mode == "contextual"
