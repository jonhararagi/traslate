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
    assert sources["licensed_english_web_novel"]["url"] == "https://global.novelpia.com/novel/41?sid=main1"
    assert sources["licensed_english_web_novel"]["chapter_count_observed"] == 1567
    assert sources["licensed_english_web_novel"]["completion_status_observed"] == "completed"
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


def test_profile_terms_have_evidence_class_suggestions_and_human_review_requirements():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert profile["candidate_review_policy"]["automatic_approval"] is False
    assert "metadato" in profile["candidate_review_policy"]["principle"].lower()
    assert all(item["approved"] is False for item in profile["terminology_candidates"])
    candidates = {item["source"]: item for item in profile["terminology_candidates"]}
    assert "I Became the Academy Villain's Daughter" not in candidates
    assert "lvl" in candidates
    for term, expected_rule in {
        "Oknodie": "protect",
        "farm": "contextual",
        "farmed": "contextual",
        "farming": "contextual",
        "steal": "contextual",
        "Steal skill": "contextual",
        "level": "contextual",
        "tsundere": "preserve",
    }.items():
        candidate = candidates[term]
        assert candidate["suggested_rule"] == expected_rule
        assert candidate["evidence_class"] in {
            "publisher_metadata_only", "user_requested_term", "genre_convention_only"
        }
        assert candidate["chapter_evidence_required"] is True
        assert candidate["evidence_status"] == "profile-only-not-verified-in-imported-chapter"
        assert candidate["review_requirements"]

def test_chapter_181_201_terminology_candidates_keep_source_provenance_and_stay_unapproved():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    evidence_candidates = [
        item for item in profile["terminology_candidates"]
        if item.get("chapter_evidence")
    ]

    # Candidates from the lab may aid review, but must not become auto-translation rules.
    assert len(evidence_candidates) >= 40
    assert all(item.get("approved") is False for item in evidence_candidates)
    allowed_evidence_states = {
        "chapter-evidence-present-pending-bilingual-review",
        "source-excerpt-present-pending-bilingual-review",
    }
    assert all(
        item.get("chapter_evidence_required") is True
        and item.get("evidence_status") in allowed_evidence_states
        for item in evidence_candidates
    )
    assert all(
        evidence_item.get("chapter_id")
        and evidence_item.get("source_file")
        and evidence_item.get("source_excerpt")
        for item in evidence_candidates
        for evidence_item in item.get("chapter_evidence", [])
    )
    evidence = [
        excerpt
        for item in evidence_candidates
        for excerpt in item.get("chapter_evidence", [])
    ]
    assert any(item.get("chapter_id") == "V02-C141" for item in evidence)
    assert any(item.get("chapter_id") == "V02-C160" for item in evidence)
    assert any(item.get("chapter_id") == "V02-C161" for item in evidence)
    assert any(item.get("chapter_id") == "V02-C180" for item in evidence)
    assert any(item.get("chapter_id") == "V02-C182" for item in evidence)
    assert any(item.get("chapter_id") == "V02-C183" for item in evidence)
    assert any(item.get("chapter_id") == "V03-C201" for item in evidence)
    assert not any(
        item["source"].casefold() == "infinite respect"
        and any(e["chapter_id"] == "V02-C176" for e in item.get("chapter_evidence", []))
        for item in evidence_candidates
    )
    feed_raider = next(item for item in evidence_candidates if item["source"].casefold() == "feed raider")
    assert any(item["chapter_id"] == "V02-C186" and item["source_excerpt"] == "Feed Raider" for item in feed_raider["chapter_evidence"])
