from __future__ import annotations

import json
from uuid import uuid4

from fastapi.testclient import TestClient

from noveltrad import main


def _add_book(source_text: str) -> str:
    book_id = str(uuid4())
    now = "2026-10-15T00:00:00+00:00"
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
            (book_id, "Candidate extraction test", "epub", "authorized-test.epub", "unused", now),
        )
        conn.execute(
            "INSERT INTO chapters(id,book_id,chapter_index,title,original_text,translated_text,status) "
            "VALUES(?,?,?,?,?,?,?)",
            (str(uuid4()), book_id, 0, "Chapter One", source_text, "", "imported"),
        )
    return book_id


def test_profile_resource_resolves_for_source_and_pyinstaller_layout(tmp_path):
    source_root = tmp_path / "checkout"
    source_module = source_root / "src" / "noveltrad" / "main.py"
    source_profile = source_root / "data" / "novels" / "i_became_the_academy_villains_daughter.json"
    source_profile.parent.mkdir(parents=True)
    source_profile.write_text("{}", encoding="utf-8")
    assert main._resolve_novel_profile_path(source_module) == source_profile

    app_root = tmp_path / "NovelTrad"
    frozen_module = app_root / "_internal" / "noveltrad" / "main.py"
    bundled_profile = app_root / "_internal" / "data" / "novels" / "i_became_the_academy_villains_daughter.json"
    bundled_profile.parent.mkdir(parents=True)
    bundled_profile.write_text("{}", encoding="utf-8")
    assert main._resolve_novel_profile_path(frozen_module) == bundled_profile


def test_extraction_cites_original_evidence_and_requires_explicit_approval(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-data"))
    main.init_db()
    source = (
        "Oknodie picked the Steal skill and began to farm for resources. "
        "The tsundere rival objected. "
    ) * 4
    original_book_id = _add_book(source)

    def should_not_call_model(*args, **kwargs):
        raise AssertionError("Candidate extraction must not invoke the translation model.")

    monkeypatch.setattr(main, "_translate_with_local_model", should_not_call_model)
    with TestClient(main.app) as client:
        extracted = client.post(f"/api/books/{original_book_id}/glossary/candidates/extract")
        assert extracted.status_code == 200, extracted.text
        stats = extracted.json()
        assert stats["scanned_chapters"] == 1
        assert stats["scanned_characters"] == len(source)
        assert stats["found_in_this_pass"] > 0
        assert stats["approved_automatically"] == 0

        listed = client.get(f"/api/books/{original_book_id}/glossary/candidates")
        assert listed.status_code == 200
        candidates = {item["source_term"].casefold(): item for item in listed.json()}
        for expected in ("oknodie", "steal skill", "farm", "tsundere"):
            assert expected in candidates, f"Missing candidate: {expected}"
            item = candidates[expected]
            assert item["status"] == "pending"
            assert item["occurrences"] >= 4
            assert item["evidence"]
            assert len(item["evidence"]) <= 3
            assert item["evidence"][0]["chapter_title"] == "Chapter One"
            assert item["source_term"] in item["evidence"][0]["snippet"]
            assert item["requires_human_review"] is True
            assert item["suggested_rule"] in {"preserve", "translate", "contextual", "protect"}
        assert candidates["oknodie"]["suggested_rule"] == "protect"
        assert candidates["farm"]["suggested_target"] == "farmear"
        assert candidates["farm"]["suggested_rule"] == "contextual"
        assert candidates["farm"]["profile_candidate"] is True

        # Merely extracting candidates cannot alter the glossary or chapter source.
        glossary = client.get(f"/api/books/{original_book_id}/glossary").json()
        assert not any(item["source_term"].casefold() == "oknodie" for item in glossary)
        with main.connection() as conn:
            chapter = conn.execute(
                "SELECT original_text, translated_text FROM chapters WHERE book_id = ?",
                (original_book_id,),
            ).fetchone()
        assert chapter["original_text"] == source
        assert chapter["translated_text"] == ""

        oknodie = candidates["oknodie"]
        approved = client.post(
            f"/api/books/{original_book_id}/glossary/candidates/{oknodie['id']}/approve",
            json={
                "preferred_term": "Oknodie",
                "rule": "protect",
                "notes": "Nombre propio; conservar la grafía de la edición importada.",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["glossary_entry"]["approved"] in (True, 1)
        assert approved.json()["glossary_entry"]["rule"] == "protect"

        glossary = client.get(f"/api/books/{original_book_id}/glossary").json()
        active = next(item for item in glossary if item["source_term"].casefold() == "oknodie")
        assert active["approved"] in (True, 1)
        assert active["preferred_term"] == "Oknodie"

        repeated = client.post(f"/api/books/{original_book_id}/glossary/candidates/extract")
        assert repeated.status_code == 200
        refreshed = client.get(
            f"/api/books/{original_book_id}/glossary/candidates?status=approved"
        ).json()
        assert any(item["id"] == oknodie["id"] for item in refreshed)

        duplicate_approval = client.post(
            f"/api/books/{original_book_id}/glossary/candidates/{oknodie['id']}/approve",
            json={"preferred_term": "Oknodie", "rule": "protect", "notes": ""},
        )
        assert duplicate_approval.status_code == 409


def test_ignored_candidate_stays_ignored_after_a_rescan(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-data"))
    main.init_db()
    source = ("The tsundere character mentions Oknodie. " * 4)
    book_id = _add_book(source)

    with TestClient(main.app) as client:
        assert client.post(f"/api/books/{book_id}/glossary/candidates/extract").status_code == 200
        candidates = client.get(f"/api/books/{book_id}/glossary/candidates").json()
        tsundere = next(item for item in candidates if item["source_term"].casefold() == "tsundere")
        ignored = client.post(f"/api/books/{book_id}/glossary/candidates/{tsundere['id']}/ignore")
        assert ignored.status_code == 200
        assert ignored.json()["status"] == "ignored"

        rescanned = client.post(f"/api/books/{book_id}/glossary/candidates/extract")
        assert rescanned.status_code == 200
        pending = client.get(f"/api/books/{book_id}/glossary/candidates").json()
        assert not any(item["id"] == tsundere["id"] for item in pending)
        ignored_list = client.get(
            f"/api/books/{book_id}/glossary/candidates?status=ignored"
        ).json()
        assert any(item["id"] == tsundere["id"] for item in ignored_list)


def test_profile_seed_requires_chapter_evidence_before_human_confirmation(monkeypatch, tmp_path):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-data"))
    main.init_db()
    source = ("Oknodie picked the Steal skill and began to farm for resources. " * 4)
    book_id = _add_book(source)
    profile = json.loads(main.NOVEL_PROFILE_PATH.read_text(encoding="utf-8"))

    with main.connection() as conn:
        conn.execute("UPDATE books SET title = ? WHERE id = ?", (profile["display_title"], book_id))
        seeded_count = main._seed_novel_profile_candidates(conn, book_id, profile["display_title"])
        seeded = conn.execute(
            "SELECT id, source_term, preferred_term, rule, notes, approved FROM glossary_entries "
            "WHERE book_id = ? AND source_term = 'Oknodie' COLLATE NOCASE",
            (book_id,),
        ).fetchone()
    assert seeded_count == len(profile["terminology_candidates"])
    assert seeded is not None
    assert seeded["approved"] in (False, 0)
    assert seeded["rule"] == "protect"
    assert "ocurrencia literal" in seeded["notes"].lower()

    now = "2026-10-17T00:00:00+00:00"
    empty_candidate_id = str(uuid4())
    with main.connection() as conn:
        conn.execute(
            "INSERT INTO glossary_candidates(id, book_id, normalized_term, source_term, category, occurrences, "
            "evidence_json, candidate_notes, status, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,'pending',?,?)",
            (
                empty_candidate_id, book_id, "oknodie", "Oknodie", "character", 0, "[]",
                "Synthetic empty-evidence row for the guard test.", now, now,
            ),
        )

    with TestClient(main.app) as client:
        bypass = client.put(
            f"/api/books/{book_id}/glossary/{seeded['id']}",
            json={
                "source_term": "Oknodie", "preferred_term": "Oknodie",
                "rule": "protect", "notes": seeded["notes"], "approved": True,
            },
        )
        assert bypass.status_code == 422
        no_evidence_approval = client.post(
            f"/api/books/{book_id}/glossary/candidates/{empty_candidate_id}/approve",
            json={"preferred_term": "Oknodie", "rule": "protect", "notes": "Confirmado en el original."},
        )
        assert no_evidence_approval.status_code == 422

        extracted = client.post(f"/api/books/{book_id}/glossary/candidates/extract")
        assert extracted.status_code == 200, extracted.text
        assert extracted.json()["approved_automatically"] == 0
        candidates = client.get(f"/api/books/{book_id}/glossary/candidates").json()
        oknodie = next(item for item in candidates if item["source_term"].casefold() == "oknodie")
        assert oknodie["id"] == empty_candidate_id
        assert oknodie["evidence"] and oknodie["suggested_rule"] == "protect"

        approved = client.post(
            f"/api/books/{book_id}/glossary/candidates/{empty_candidate_id}/approve",
            json={
                "preferred_term": "Oknodie",
                "rule": "protect",
                "notes": "Nombre propio; grafía revisada en la muestra literal del capítulo.",
            },
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "approved"
        assert approved.json()["glossary_entry"]["approved"] in (True, 1)

    with main.connection() as conn:
        final_entry = conn.execute(
            "SELECT preferred_term, rule, approved FROM glossary_entries WHERE id = ?", (seeded["id"],)
        ).fetchone()
    assert final_entry["preferred_term"] == "Oknodie"
    assert final_entry["rule"] == "protect"
    assert final_entry["approved"] in (True, 1)
