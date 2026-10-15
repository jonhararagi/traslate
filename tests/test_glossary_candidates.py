from __future__ import annotations

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
