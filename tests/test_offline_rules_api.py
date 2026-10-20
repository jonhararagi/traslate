import fitz
import pytest
from fastapi.testclient import TestClient

from noveltrad import main as main_module
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


def test_reader_exposes_offline_preview_and_keeps_manual_assistance_options(offline_client):
    page = offline_client.get("/").text
    assert 'id="offline-rules-open"' in page
    assert 'id="offline-profile"' in page
    assert 'value="light_novel_es"' in page
    assert 'value="faithful_literary_es"' in page
    assert 'value="webnovel_es"' in page
    assert 'id="translation-mode"' in page
    assert 'value="local"' in page
    assert 'value="premium"' in page
    assert "Ollama" in page
    assert "3.500 caracteres" in page
    assert 'id="offline-chunks"' in page
    assert "fragmentos secuenciales" in page
    assert "Proponer traducción al español" in page
    assert "Analizar contexto, personajes y relaciones" in page
    assert "Revisar continuidad sin inventar canon" in page
    assert "Revisar estilo y claridad" in page
    assert "Extraer términos candidatos para el glosario" in page



def test_premium_mode_is_local_preview_and_does_not_save(offline_client, monkeypatch):
    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", _pdf_with_text("Oknodie entered the academy."), "application/pdf")},
    ).json()
    chapter = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    calls = []

    def fake_local_model(text, glossary):
        calls.append((text, glossary))
        return "Oknodie entró en la academia."

    monkeypatch.setattr(main_module, "_translate_with_local_model", fake_local_model)
    preview = offline_client.post(f"/api/chapters/{chapter['id']}/premium-translation-preview")
    assert preview.status_code == 200, preview.text
    payload = preview.json()
    assert payload["mode"] == "premium-local-neural"
    assert payload["preview_only"] is True
    assert payload["saved"] is False
    assert payload["text"] == "Oknodie entró en la academia."
    assert len(calls) == 1
    reread = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    assert reread["translated_text"] == ""


def test_premium_mode_missing_chapter_returns_404(offline_client):
    response = offline_client.post("/api/chapters/missing/premium-translation-preview")
    assert response.status_code == 404



def test_importing_first_novel_seeds_only_unapproved_profile_candidates(offline_client):
    imported = offline_client.post(
        "/api/books/import",
        files={
            "file": (
                "I Became the Academy Villain's Daughter.pdf",
                _pdf_with_text("Oknodie entered the academy."),
                "application/pdf",
            )
        },
    )
    assert imported.status_code == 200, imported.text
    payload = imported.json()
    assert payload["unapproved_profile_candidates"] >= 3

    glossary = offline_client.get(f"/api/books/{payload['id']}/glossary")
    assert glossary.status_code == 200
    entries = glossary.json()
    candidates = {entry["source_term"]: entry for entry in entries}
    assert "Oknodie" in candidates
    assert candidates["Oknodie"]["approved"] == 0
    assert candidates["Oknodie"]["rule"] == "protect"
    assert "no aprobado" in candidates["Oknodie"]["notes"].lower()


def test_unrelated_book_does_not_receive_first_novel_candidates(offline_client):
    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("Different Novel.pdf", _pdf_with_text("A hero arrived."), "application/pdf")},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["unapproved_profile_candidates"] == 0
    glossary = offline_client.get(f"/api/books/{imported.json()['id']}/glossary")
    assert glossary.status_code == 200
    assert glossary.json() == []



def test_premium_unavailable_runtime_returns_503_without_remote_fallback(offline_client, monkeypatch):
    import urllib.error

    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", _pdf_with_text("Oknodie entered the academy."), "application/pdf")},
    ).json()
    chapter = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    requested_urls = []

    def unavailable(request, timeout):
        requested_urls.append(request.full_url)
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", unavailable)
    response = offline_client.post(f"/api/chapters/{chapter['id']}/premium-translation-preview")
    assert response.status_code == 503
    assert "No se contactó ningún servicio remoto" in response.json()["detail"]
    assert requested_urls == ["http://127.0.0.1:11434/api/generate"]


def test_premium_timeout_returns_503_and_never_saves(offline_client, monkeypatch):
    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", _pdf_with_text("Oknodie entered the academy."), "application/pdf")},
    ).json()
    chapter = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]

    def timed_out(request, timeout):
        raise TimeoutError("local model timeout")

    monkeypatch.setattr("urllib.request.urlopen", timed_out)
    response = offline_client.post(f"/api/chapters/{chapter['id']}/premium-translation-preview")
    assert response.status_code == 503
    assert "No se contactó ningún servicio remoto" in response.json()["detail"]
    reread = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    assert reread["translated_text"] == ""


def test_premium_oversized_chapter_is_rejected_before_model_call(offline_client, monkeypatch):
    imported = offline_client.post(
        "/api/books/import",
        files={"file": ("sample.pdf", _pdf_with_text("Oknodie entered the academy."), "application/pdf")},
    ).json()
    chapter = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    monkeypatch.setattr(main_module, "PREMIUM_PREVIEW_MAX_CHARS", 10)

    def should_not_run(*args, **kwargs):
        raise AssertionError("Premium model must not run for oversized input")

    monkeypatch.setattr(main_module, "_translate_with_local_model", should_not_run)
    response = offline_client.post(f"/api/chapters/{chapter['id']}/premium-translation-preview")
    assert response.status_code == 413
    assert "limitar RAM/contexto" in response.json()["detail"]
    reread = offline_client.get(f"/api/books/{imported['id']}/chapters").json()[0]
    assert reread["translated_text"] == ""
