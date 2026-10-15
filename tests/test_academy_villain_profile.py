import json
from pathlib import Path

from noveltrad.narrative_rules import TermRule, apply_offline_rules


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "data" / "novels" / "i_became_the_academy_villains_daughter.json"
BENCHMARK_PATH = ROOT / "data" / "benchmarks" / "academy_villain_context_cases.json"


def test_first_novel_profile_links_official_sources_and_keeps_terms_unapproved():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    sources = {item["format"]: item for item in profile["source_catalog"]}
    assert sources["original_web_novel"]["url"] == "https://novelpia.com/novel/96311"
    assert sources["licensed_comic_adaptation"]["url"].startswith("https://tapas.io/")
    candidates = {item["source"]: item for item in profile["terminology_candidates"]}
    for term in ("Oknodie", "farm", "farmed", "farming", "steal", "Steal skill", "level", "tsundere", "min-maxing"):
        assert term in candidates
        assert candidates[term]["approved"] is False


def test_context_benchmark_is_labeled_synthetic_and_covers_ambiguity():
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    assert benchmark["status"] == "synthetic-diagnostic-cases-not-excerpts-from-the-novel"
    cases = {case["id"]: case for case in benchmark["cases"]}
    assert cases["farm-001"]["source"] != cases["farm-002"]["source"]
    assert "farm_as_gaming_grind" in cases["farm-001"]["checks"]
    assert "farm_as_physical_place" in cases["farm-002"]["checks"]
    assert "possible_skill_name_preserved" in cases["steal-001"]["checks"]
    assert len(cases) >= 8


def test_unapproved_novel_candidates_do_not_mutate_text():
    # Matches the current app contract: candidate terms do nothing until approved.
    result = apply_offline_rules(
        "Oknodie farmed monsters and tried to steal a key.",
        term_rules=[
            TermRule("Oknodie", "Oknodie", "preserve", approved=False),
            TermRule("farm", "farmear", "translate", approved=False),
            TermRule("steal", "robar", "translate", approved=False),
        ],
        normalize_typography=False,
    )
    assert result.text == "Oknodie farmed monsters and tried to steal a key."
