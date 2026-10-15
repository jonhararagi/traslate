import fitz
import pytest
from fastapi.testclient import TestClient

from noveltrad.main import app


@pytest.fixture()
def offline_client(tmp_path, monkeypatch):
    monkeypatch.setenv("NOVELTRAD_HOME", str(tmp_path / "noveltrad-offline-data"))
    with TestClient(app) as client:
        yield client


def _pdf_with_text(text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 520, 720), text)
    data = document.tobytes()
    document.close()
    return data


def test_api_offline_rules_preview_uses_only_approved_glossary_and_does_not_save(offline_client):
    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", _pdf_with_text("Anzu reached level 10."), "application/pdf")},
    ).json()
    chapter = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    glossary_url = f"/api/books/{imported['id']}/glossary"

    approved = offline_client.post(
        glossary_url,
        json={"source_term": "level", "preferred_term": "nivel", "rule": "translate", "approved": True},
    )
    pending = offline_client.post(
        glossary_url,
        json={"source_term": "Anzu", "preferred_term": "Anzu cambiado", "rule": "translate", "approved": False},
    )
    assert approved.status_code == 200
    assert pending.status_code == 200

    preview = offline_client.post(
        f"/api/chapters/{chapter['id']}/offline-rules",
        json={"profile_id": "light_novel_es", "phrase_map": {"reached": "alcanzó"}},
    )
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["mode"] == "deterministic-offline-rules"
    assert payload["preview_only"] is True
    assert payload["saved"] is False
    assert payload["text"] == "Anzu alcanzó nivel 10."
    reread = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    assert reread["translated_text"] == ""


def test_api_offline_rules_rejects_unknown_profile_and_missing_chapter(offline_client):
    bad_profile = offline_client.post(
        "/api/chapters/missing/offline-rules",
        json={"profile_id": "invented-profile"},
    )
    assert bad_profile.status_code == 422
    missing = offline_client.post(
        "/api/chapters/missing/offline-rules",
        json={"profile_id": "webnovel_es"},
    )
    assert missing.status_code == 404
