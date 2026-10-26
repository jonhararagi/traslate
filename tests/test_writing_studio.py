from contextlib import contextmanager
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from noveltrad.writing_studio import install_writing_studio_routes


def _client(tmp_path):
    db_path = tmp_path / "writing-studio.sqlite3"

    @contextmanager
    def connection():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    app = FastAPI()
    install_writing_studio_routes(app, connection)
    return TestClient(app)


def _project(client):
    response = client.post(
        "/api/writing/projects",
        json={
            "title": "La torre de ceniza",
            "genre": "Fantasía",
            "language": "es",
            "style_guide": "Tercera persona limitada. Prosa clara.",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_writing_project_and_memory_require_explicit_canon_approval(tmp_path):
    client = _client(tmp_path)
    project = _project(client)

    memory_response = client.post(
        f"/api/writing/projects/{project['id']}/memory",
        json={
            "kind": "character",
            "title": "Lía",
            "content": "Lía puede oír las campanas enterradas, pero no controlar el tiempo.",
            "keywords": "Lía campanas",
            "source_ref": "Decisión inicial del autor",
        },
    )
    assert memory_response.status_code == 200
    memory = memory_response.json()
    assert memory["status"] == "proposed"

    prompt_payload = {
        "role": "coauthor",
        "user_instruction": "Escribe una escena en la torre con Lía y las campanas.",
    }
    unapproved = client.post(f"/api/writing/projects/{project['id']}/prompt", json=prompt_payload)
    assert unapproved.status_code == 200
    assert unapproved.json()["memory_count"] == 0
    assert "Lía puede oír" not in unapproved.json()["prompt"]
    assert unapproved.json()["provider_submission"] == "manual_only"
    assert unapproved.json()["saved_automatically"] is False

    approval = client.post(
        f"/api/writing/memory/{memory['id']}/status",
        json={"status": "approved"},
    )
    assert approval.status_code == 200
    assert approval.json()["status"] == "approved"

    approved = client.post(f"/api/writing/projects/{project['id']}/prompt", json=prompt_payload)
    assert approved.status_code == 200
    response = approved.json()
    assert response["memory_count"] == 1
    assert memory["id"] in response["prompt"]
    assert "Lía puede oír" in response["prompt"]
    assert response["memory_used"][0]["id"] == memory["id"]

    rejected = client.post(
        f"/api/writing/memory/{memory['id']}/status",
        json={"status": "rejected"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    after_rejection = client.post(f"/api/writing/projects/{project['id']}/prompt", json=prompt_payload)
    assert after_rejection.status_code == 200
    assert after_rejection.json()["memory_count"] == 0
    assert "Lía puede oír" not in after_rejection.json()["prompt"]


def test_writing_chapters_are_drafts_and_versions_preserve_previous_text(tmp_path):
    client = _client(tmp_path)
    project = _project(client)

    created = client.post(
        f"/api/writing/projects/{project['id']}/chapters",
        json={"title": "Capítulo 1", "content": "Lía oyó la primera campana."},
    )
    assert created.status_code == 200
    chapter = created.json()
    assert chapter["chapter_number"] == 1
    assert chapter["current_version"] == 1
    assert chapter["status"] == "draft"

    edited = client.put(
        f"/api/writing/chapters/{chapter['id']}",
        json={"title": "Capítulo 1 — La campana", "content": "Lía oyó tres campanas bajo tierra."},
    )
    assert edited.status_code == 200
    assert edited.json()["current_version"] == 2
    assert edited.json()["content"] == "Lía oyó tres campanas bajo tierra."
    assert edited.json()["status"] == "draft"

    versions = client.get(f"/api/writing/chapters/{chapter['id']}/versions")
    assert versions.status_code == 200
    values = {version["version_number"]: version for version in versions.json()}
    assert values[1]["title"] == "Capítulo 1"
    assert values[1]["content"] == "Lía oyó la primera campana."
    assert values[2]["title"] == "Capítulo 1 — La campana"
    assert values[2]["content"] == "Lía oyó tres campanas bajo tierra."

    listed = client.get(f"/api/writing/projects/{project['id']}/chapters")
    assert listed.status_code == 200
    assert listed.json()[0]["current_version"] == 2


def test_writing_api_rejects_unknown_projects_and_blank_memory(tmp_path):
    client = _client(tmp_path)

    unknown = client.get("/api/writing/projects/does-not-exist/memory")
    assert unknown.status_code == 404

    project = _project(client)
    blank = client.post(
        f"/api/writing/projects/{project['id']}/memory",
        json={"kind": "lore", "title": "Empty", "content": "   "},
    )
    assert blank.status_code == 422

    invalid_status = client.post(
        "/api/writing/memory/unknown/status",
        json={"status": "approved"},
    )
    assert invalid_status.status_code == 404



def test_editing_approved_memory_reverts_it_to_proposal(tmp_path):
    client = _client(tmp_path)
    project = _project(client)
    created = client.post(
        f"/api/writing/projects/{project['id']}/memory",
        json={
            "kind": "rule",
            "title": "Magic rule",
            "content": "The bell can reveal hidden paths.",
            "keywords": "bell magic",
            "source_ref": "Author note 1",
        },
    )
    assert created.status_code == 200
    item = created.json()
    approved = client.post(f"/api/writing/memory/{item['id']}/status", json={"status": "approved"})
    assert approved.status_code == 200

    edited = client.put(
        f"/api/writing/memory/{item['id']}",
        json={
            "kind": "rule",
            "title": "Magic rule revised",
            "content": "The bell reveals hidden paths only during winter.",
            "keywords": "bell magic winter",
            "source_ref": "Author note 2",
        },
    )
    assert edited.status_code == 200
    value = edited.json()
    assert value["title"] == "Magic rule revised"
    assert value["content"] == "The bell reveals hidden paths only during winter."
    assert value["source_ref"] == "Author note 2"
    assert value["status"] == "proposed"

    prompt = client.post(
        f"/api/writing/projects/{project['id']}/prompt",
        json={"role": "lore_guardian", "user_instruction": "Explain the bell rule in winter."},
    )
    assert prompt.status_code == 200
    assert prompt.json()["memory_count"] == 0
    assert "only during winter" not in prompt.json()["prompt"]



def test_custom_bot_profile_is_persistent_and_controls_prompt_role(tmp_path):
    client = _client(tmp_path)
    project = _project(client)
    created = client.post(
        f"/api/writing/projects/{project['id']}/bots",
        json={
            "name": "Cronista sobrio",
            "role": "continuity_editor",
            "provider": "gemini",
            "instructions": "Usa frases cortas. Nunca completes un vacío de canon con una suposición.",
        },
    )
    assert created.status_code == 200
    bot = created.json()
    assert bot["name"] == "Cronista sobrio"
    assert bot["provider"] == "gemini"

    listed = client.get(f"/api/writing/projects/{project['id']}/bots")
    assert listed.status_code == 200
    assert any(entry["id"] == bot["id"] for entry in listed.json())

    prompt = client.post(
        f"/api/writing/projects/{project['id']}/prompt",
        json={
            "role": "coauthor",
            "bot_id": bot["id"],
            "user_instruction": "Revisa si el alcalde causó el silencio de la campana.",
        },
    )
    assert prompt.status_code == 200
    result = prompt.json()
    assert result["role"] == "continuity_editor"
    assert result["bot"]["name"] == "Cronista sobrio"
    assert "Nunca completes un vacío de canon con una suposición." in result["prompt"]
    assert "Actúa como editor de continuidad." in result["prompt"]
    assert result["provider_submission"] == "manual_only"

    edited = client.put(
        f"/api/writing/bots/{bot['id']}",
        json={
            "name": "Cronista preciso",
            "role": "lore_guardian",
            "provider": "chatgpt",
            "instructions": "Contesta solo con evidencia confirmada.",
        },
    )
    assert edited.status_code == 200
    assert edited.json()["name"] == "Cronista preciso"
    assert edited.json()["role"] == "lore_guardian"

    updated_prompt = client.post(
        f"/api/writing/projects/{project['id']}/prompt",
        json={"role": "coauthor", "bot_id": bot["id"], "user_instruction": "Consulta el canon."},
    )
    assert updated_prompt.status_code == 200
    assert updated_prompt.json()["role"] == "lore_guardian"
    assert "Contesta solo con evidencia confirmada." in updated_prompt.json()["prompt"]

    deleted = client.delete(f"/api/writing/bots/{bot['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    missing = client.post(
        f"/api/writing/projects/{project['id']}/prompt",
        json={"bot_id": bot["id"], "user_instruction": "Consulta el canon."},
    )
    assert missing.status_code == 404
