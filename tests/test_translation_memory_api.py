import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from noveltrad.translation_memory_api import install_translation_memory_routes


def _client(tmp_path):
    app = FastAPI()
    install_translation_memory_routes(app, lambda: tmp_path)
    return TestClient(app)


def _page_pack(*, claimed_status="confirmed"):
    records = [
        {
            "id": "SYNTH-C001-P01",
            "chapter_id": "SYNTH-C001",
            "page_index": 1,
            "chapter_page_count": 2,
            "chapter_ends_with_page_separator": True,
            "source_text": "Synthetic opening page.",
            "target_text": "Página sintética inicial.",
            "status": claimed_status,
            "source_blob_sha": "source-sha-example",
            "translation_blob_sha": "translation-sha-example",
        },
        {
            "id": "SYNTH-C001-P02",
            "chapter_id": "SYNTH-C001",
            "page_index": 2,
            "chapter_page_count": 2,
            "chapter_ends_with_page_separator": True,
            "source_text": "Second synthetic page.",
            "target_text": "Segunda página sintética.",
            "status": claimed_status,
            "source_blob_sha": "source-sha-example",
            "translation_blob_sha": "translation-sha-example",
        },
    ]
    return ("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n").encode("utf-8")


def test_import_downgrades_all_records_to_draft_and_does_not_apply(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(), "application/x-ndjson")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_records"] == 2
    assert payload["imported"] == 2
    assert payload["imported_status"] == "draft"
    assert payload["explicit_approval_required"] is True
    assert payload["applied_to_chapters"] is False

    listed = client.get("/api/books/book-synthetic/translation-memory").json()
    assert listed["count"] == 2
    assert {entry["status"] for entry in listed["entries"]} == {"draft"}
    assert {entry["review_status"] for entry in listed["entries"]} == {"imported_pending_review"}
    # Listing is metadata-only: private source/target text is not returned.
    assert "source_text" not in listed["entries"][0]
    assert "target_text" not in listed["entries"][0]


def test_preview_requires_complete_exact_chapter_match_and_is_never_automatic(tmp_path):
    client = _client(tmp_path)
    imported = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(), "application/jsonl")},
    )
    assert imported.status_code == 200

    source = "Synthetic opening page.\fSecond synthetic page.\f"
    default_preview = client.post(
        "/api/books/book-synthetic/translation-memory/preview",
        json={"source_text": source, "chapter_ref": "SYNTH-C001"},
    )
    assert default_preview.status_code == 200
    assert default_preview.json()["matched"] is False

    draft_preview = client.post(
        "/api/books/book-synthetic/translation-memory/preview",
        json={"source_text": source, "chapter_ref": "SYNTH-C001", "include_draft": True},
    )
    assert draft_preview.status_code == 200
    body = draft_preview.json()
    assert body["matched"] is True
    assert body["complete"] is True
    assert body["coverage"] == 1.0
    assert body["memory_status"] == "draft"
    assert body["proposed_text"] == "Página sintética inicial.\fSegunda página sintética.\f"
    assert body["preview_only"] is True
    assert body["saved"] is False
    assert body["auto_applied"] is False

    partial = client.post(
        "/api/books/book-synthetic/translation-memory/preview",
        json={"source_text": "Synthetic opening page.", "include_draft": True},
    )
    assert partial.status_code == 200
    assert partial.json()["matched"] is False


def test_approval_is_explicit_and_still_only_proposes_memory(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(claimed_status="rejected"), "application/jsonl")},
    )
    assert response.status_code == 200

    for entry_id in ("SYNTH-C001-P01", "SYNTH-C001-P02"):
        approval = client.post(
            f"/api/books/book-synthetic/translation-memory/{entry_id}/approve"
        )
        assert approval.status_code == 200
        assert approval.json()["status"] == "confirmed"
        assert approval.json()["applied_to_chapters"] is False

    preview = client.post(
        "/api/books/book-synthetic/translation-memory/preview",
        json={
            "source_text": "Synthetic opening page.\fSecond synthetic page.\f",
            "chapter_ref": "SYNTH-C001",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["matched"] is True
    assert preview.json()["memory_status"] == "confirmed"
    assert preview.json()["saved"] is False


def test_invalid_jsonl_returns_422_and_duplicate_import_is_idempotent(tmp_path):
    client = _client(tmp_path)
    invalid = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("broken.jsonl", b"{not json}\n", "application/jsonl")},
    )
    assert invalid.status_code == 422

    first = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(), "application/jsonl")},
    )
    second = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(), "application/jsonl")},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["imported"] == 0
    assert second.json()["skipped_existing"] == 2
    assert client.get("/api/books/book-synthetic/translation-memory").json()["count"] == 2


def test_only_jsonl_or_ndjson_files_are_accepted(tmp_path):
    client = _client(tmp_path)
    response = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.txt", _page_pack(), "text/plain")},
    )
    assert response.status_code == 415


def test_import_rejects_incomplete_chapter_page_set(tmp_path):
    client = _client(tmp_path)
    incomplete = [
        {
            "id": "SYNTH-C002-P01",
            "chapter_id": "SYNTH-C002",
            "page_index": 1,
            "chapter_page_count": 3,
            "chapter_ends_with_page_separator": True,
            "source_text": "Page one.",
            "target_text": "Página uno.",
            "status": "draft",
        },
        {
            "id": "SYNTH-C002-P02",
            "chapter_id": "SYNTH-C002",
            "page_index": 2,
            "chapter_page_count": 3,
            "chapter_ends_with_page_separator": True,
            "source_text": "Page two.",
            "target_text": "Página dos.",
            "status": "draft",
        },
    ]
    response = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={
            "file": (
                "incomplete.jsonl",
                ("\n".join(json.dumps(record) for record in incomplete) + "\n").encode("utf-8"),
                "application/jsonl",
            )
        },
    )
    assert response.status_code == 422
    assert "incompleto" in response.json()["detail"]
    assert client.get("/api/books/book-synthetic/translation-memory").json()["count"] == 0


def test_single_entry_review_endpoint_returns_only_the_requested_page_and_is_book_scoped(tmp_path):
    client = _client(tmp_path)
    imported = client.post(
        "/api/books/book-synthetic/translation-memory/import",
        files={"file": ("sample.jsonl", _page_pack(), "application/x-ndjson")},
    )
    assert imported.status_code == 200

    detail = client.get(
        "/api/books/book-synthetic/translation-memory/SYNTH-C001-P01"
    )
    assert detail.status_code == 200
    body = detail.json()
    assert body["entry"]["source_text"] == "Synthetic opening page."
    assert body["entry"]["target_text"] == "Página sintética inicial."
    assert body["entry"]["status"] == "draft"
    assert body["review_only"] is True
    assert body["applied_to_chapters"] is False
    assert body["explicit_decision_required"] is True

    wrong_book = client.get(
        "/api/books/another-book/translation-memory/SYNTH-C001-P01"
    )
    assert wrong_book.status_code == 404

    # The bulk listing stays metadata-only; the prose is returned only on review.
    listing = client.get("/api/books/book-synthetic/translation-memory").json()
    assert "source_text" not in listing["entries"][0]
    assert "target_text" not in listing["entries"][0]
