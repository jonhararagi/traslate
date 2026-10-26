"""Persistent writing-project memory and manual AI prompt handoff.

This module stores original-fiction projects separately from imported books and
translation records. It never calls an AI provider or submits text automatically.
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

ConnectionFactory = Callable[[], AbstractContextManager]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _init_tables(connection_factory: ConnectionFactory) -> None:
    with connection_factory() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS writing_projects (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                genre TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT 'es',
                style_guide TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS writing_bots (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('coauthor','lore_guardian','continuity_editor','language_editor','planner')),
                provider TEXT NOT NULL DEFAULT 'chatgpt' CHECK(provider IN ('chatgpt','gemini')),
                instructions TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, name)
            );
            CREATE INDEX IF NOT EXISTS idx_writing_bots_project ON writing_bots(project_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS writing_memory_items (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE,
                kind TEXT NOT NULL CHECK(kind IN ('character','lore','location','rule','timeline','plot','language','object','relationship','other')),
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT NOT NULL DEFAULT '',
                source_ref TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved','rejected','conflict')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_writing_memory_project_status
                ON writing_memory_items(project_id, status, updated_at DESC);
            CREATE TABLE IF NOT EXISTS writing_chapters (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES writing_projects(id) ON DELETE CASCADE,
                chapter_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','ready')),
                current_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(project_id, chapter_number)
            );
            CREATE INDEX IF NOT EXISTS idx_writing_chapters_project_order
                ON writing_chapters(project_id, chapter_number);
            CREATE TABLE IF NOT EXISTS writing_chapter_versions (
                id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL REFERENCES writing_chapters(id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(chapter_id, version_number)
            );
            """
        )


class WritingProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    genre: str = Field(default='', max_length=120)
    language: str = Field(default='es', pattern='^(es|en|ja|ko|other)$')
    style_guide: str = Field(default='', max_length=12000)

    @field_validator('title', 'genre', 'style_guide', mode='before')
    @classmethod
    def normalize_project_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class WritingMemoryInput(BaseModel):
    kind: str = Field(pattern='^(character|lore|location|rule|timeline|plot|language|object|relationship|other)$')
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=12000)
    keywords: str = Field(default='', max_length=1000)
    source_ref: str = Field(default='', max_length=1000)

    @field_validator('title', 'keywords', 'source_ref', mode='before')
    @classmethod
    def normalize_memory_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator('content')
    @classmethod
    def memory_content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('La ficha de memoria no puede estar vacía.')
        return value


class WritingMemoryStatusInput(BaseModel):
    status: str = Field(pattern='^(approved|rejected|conflict)$')


class WritingChapterInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100000)
    chapter_number: int | None = Field(default=None, ge=1, le=5000)

    @field_validator('title', mode='before')
    @classmethod
    def normalize_chapter_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator('content')
    @classmethod
    def chapter_content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('El borrador no puede estar vacío.')
        return value


class WritingChapterEditInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator('title', mode='before')
    @classmethod
    def normalize_chapter_title(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator('content')
    @classmethod
    def chapter_content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('El borrador no puede estar vacío.')
        return value


class WritingBotInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default='coauthor', pattern='^(coauthor|lore_guardian|continuity_editor|language_editor|planner)$')
    provider: str = Field(default='chatgpt', pattern='^(chatgpt|gemini)$')
    instructions: str = Field(default='', max_length=6000)

    @field_validator('name', 'instructions', mode='before')
    @classmethod
    def normalize_bot_fields(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class WritingPromptInput(BaseModel):
    role: str = Field(default='coauthor', pattern='^(coauthor|lore_guardian|continuity_editor|language_editor|planner)$')
    bot_id: str | None = Field(default=None, max_length=80)
    user_instruction: str = Field(min_length=1, max_length=8000)

    @field_validator('user_instruction')
    @classmethod
    def instruction_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('Escribí una instrucción para preparar el prompt.')
        return value.strip()


ROLE_INSTRUCTIONS = {
    'coauthor': (
        'Actúa como coautor literario. Redacta solo lo solicitado, en el idioma del proyecto. '
        'Respeta la biblia narrativa y el punto de vista. No conviertas propuestas nuevas en canon. '
        'Si necesitas inventar un detalle creativo para la escena, mantenlo como propuesta y no lo declares hecho establecido.'
    ),
    'lore_guardian': (
        'Actúa como guardián del lore. No escribas una escena salvo que se pida. Responde separando '
        'ESTABLECIDO, NO ESTABLECIDO, NO ENCONTRADO y CONFLICTO. Cita los identificadores [MEM:...] '
        'de la memoria proporcionada. Nunca inventes una fuente o un hecho para llenar un vacío.'
    ),
    'continuity_editor': (
        'Actúa como editor de continuidad. Compara la idea/texto solicitado con los hechos aprobados. '
        'Enumera cada contradicción con identificadores de memoria, gravedad y una alternativa no canónica. '
        'No reescribas el canon ni cambies los hechos sin permiso.'
    ),
    'language_editor': (
        'Actúa como editor de idioma y estilo. Mejora claridad, naturalidad y ritmo en el idioma del proyecto. '
        'Preserva los hechos, la focalización, la personalidad, el orden causal y el nivel de información. '
        'No añadas acciones, emociones o explicaciones que el texto no sostenga.'
    ),
    'planner': (
        'Actúa como planificador de historias. Propón premisas, objetivos de escena, arcos y pistas. '
        'Etiqueta cada idea nueva como PROPUESTA NO CANÓNICA y señala cualquier choque con la biblia.'
    ),
}

_STOPWORDS = {
    'para', 'como', 'desde', 'hasta', 'sobre', 'entre', 'este', 'esta', 'estos', 'estas',
    'donde', 'cuando', 'porque', 'pero', 'también', 'solo', 'sólo', 'que', 'con', 'sin',
    'una', 'uno', 'unos', 'unas', 'los', 'las', 'del', 'por', 'sus', 'por', 'the', 'and',
    'for', 'with', 'from', 'that', 'this', 'into', 'have', 'will', 'your',
}


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r'[\wáéíóúüñ]+', text.casefold()) if len(token) > 2 and token not in _STOPWORDS}


def _select_memories(rows: list[dict[str, object]], instruction: str, max_items: int = 30, max_chars: int = 16000) -> list[dict[str, object]]:
    query_tokens = _tokens(instruction)

    def score_row(row: dict[str, object]) -> int:
        searchable = ' '.join(str(row.get(key, '')) for key in ('title', 'content', 'keywords', 'kind'))
        return len(query_tokens & _tokens(searchable))

    # Sort ties by recency, but prioritize lexical relevance above recency.
    ordered = sorted(rows, key=lambda row: str(row.get('updated_at', '')), reverse=True)
    ordered.sort(key=score_row, reverse=True)
    selected: list[dict[str, object]] = []
    used_chars = 0
    for row in ordered:
        item_cost = len(str(row.get('title', ''))) + len(str(row.get('content', ''))) + len(str(row.get('source_ref', ''))) + 80
        if len(selected) >= max_items:
            break
        if query_tokens and score_row(row) == 0:
            continue
        if used_chars + item_cost > max_chars:
            continue
        selected.append(row)
        used_chars += item_cost
    return selected


def install_writing_studio_routes(app: FastAPI, connection_factory: ConnectionFactory) -> None:
    """Install the local writing-project API on the provided FastAPI application."""

    def ensure_tables() -> None:
        _init_tables(connection_factory)

    def require_project(conn, project_id: str):
        project = conn.execute('SELECT * FROM writing_projects WHERE id = ?', (project_id,)).fetchone()
        if project is None:
            raise HTTPException(status_code=404, detail='No se encontró el proyecto de novela.')
        return project

    @app.get('/api/writing/projects')
    def list_writing_projects() -> list[dict[str, object]]:
        ensure_tables()
        with connection_factory() as conn:
            rows = conn.execute(
                'SELECT p.id, p.title, p.genre, p.language, p.style_guide, p.created_at, p.updated_at, '
                '(SELECT COUNT(*) FROM writing_memory_items m WHERE m.project_id=p.id) AS memory_count, '
                '(SELECT COUNT(*) FROM writing_chapters c WHERE c.project_id=p.id) AS chapter_count '
                'FROM writing_projects p ORDER BY p.updated_at DESC'
            ).fetchall()
            return [dict(row) for row in rows]

    @app.post('/api/writing/projects')
    def create_writing_project(payload: WritingProjectInput) -> dict[str, object]:
        ensure_tables()
        now = _now()
        project_id = str(uuid4())
        with connection_factory() as conn:
            conn.execute(
                'INSERT INTO writing_projects(id,title,genre,language,style_guide,created_at,updated_at) '
                'VALUES (?,?,?,?,?,?,?)',
                (project_id, payload.title, payload.genre, payload.language, payload.style_guide, now, now),
            )
            row = conn.execute('SELECT * FROM writing_projects WHERE id=?', (project_id,)).fetchone()
            return dict(row)

    @app.get('/api/writing/projects/{project_id}')
    def get_writing_project(project_id: str) -> dict[str, object]:
        ensure_tables()
        with connection_factory() as conn:
            return dict(require_project(conn, project_id))

    @app.get('/api/writing/projects/{project_id}/bots')
    def list_writing_bots(project_id: str) -> list[dict[str, object]]:
        ensure_tables()
        with connection_factory() as conn:
            require_project(conn, project_id)
            rows = conn.execute(
                'SELECT * FROM writing_bots WHERE project_id=? ORDER BY updated_at DESC, name COLLATE NOCASE',
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    @app.post('/api/writing/projects/{project_id}/bots')
    def create_writing_bot(project_id: str, payload: WritingBotInput) -> dict[str, object]:
        ensure_tables()
        now = _now()
        bot_id = str(uuid4())
        with connection_factory() as conn:
            require_project(conn, project_id)
            try:
                conn.execute(
                    'INSERT INTO writing_bots(id,project_id,name,role,provider,instructions,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',
                    (bot_id, project_id, payload.name, payload.role, payload.provider, payload.instructions, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail='Ya existe un bot con ese nombre en este proyecto.') from exc
            row = conn.execute('SELECT * FROM writing_bots WHERE id=?', (bot_id,)).fetchone()
            return dict(row)

    @app.put('/api/writing/bots/{bot_id}')
    def update_writing_bot(bot_id: str, payload: WritingBotInput) -> dict[str, object]:
        ensure_tables()
        with connection_factory() as conn:
            row = conn.execute('SELECT * FROM writing_bots WHERE id=?', (bot_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='No se encontró el perfil de bot.')
            try:
                conn.execute(
                    'UPDATE writing_bots SET name=?,role=?,provider=?,instructions=?,updated_at=? WHERE id=?',
                    (payload.name, payload.role, payload.provider, payload.instructions, _now(), bot_id),
                )
            except sqlite3.IntegrityError as exc:
                raise HTTPException(status_code=409, detail='Ya existe otro bot con ese nombre en este proyecto.') from exc
            updated = conn.execute('SELECT * FROM writing_bots WHERE id=?', (bot_id,)).fetchone()
            return dict(updated)

    @app.delete('/api/writing/bots/{bot_id}')
    def delete_writing_bot(bot_id: str) -> dict[str, object]:
        ensure_tables()
        with connection_factory() as conn:
            deleted = conn.execute('DELETE FROM writing_bots WHERE id=?', (bot_id,)).rowcount
            if not deleted:
                raise HTTPException(status_code=404, detail='No se encontró el perfil de bot.')
        return {'id': bot_id, 'deleted': True}

    @app.get('/api/writing/projects/{project_id}/memory')
    def list_writing_memory(project_id: str) -> list[dict[str, object]]:
        ensure_tables()
        with connection_factory() as conn:
            require_project(conn, project_id)
            rows = conn.execute(
                'SELECT * FROM writing_memory_items WHERE project_id=? '
                'ORDER BY CASE status WHEN "proposed" THEN 0 WHEN "conflict" THEN 1 WHEN "approved" THEN 2 ELSE 3 END, updated_at DESC',
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    @app.post('/api/writing/projects/{project_id}/memory')
    def create_writing_memory(project_id: str, payload: WritingMemoryInput) -> dict[str, object]:
        ensure_tables()
        now = _now()
        item_id = str(uuid4())
        with connection_factory() as conn:
            require_project(conn, project_id)
            conn.execute(
                'INSERT INTO writing_memory_items(id,project_id,kind,title,content,keywords,source_ref,status,created_at,updated_at) '
                'VALUES (?,?,?,?,?,?,?,\'proposed\',?,?)',
                (item_id, project_id, payload.kind, payload.title, payload.content, payload.keywords, payload.source_ref, now, now),
            )
            row = conn.execute('SELECT * FROM writing_memory_items WHERE id=?', (item_id,)).fetchone()
            return dict(row)

    @app.put('/api/writing/memory/{item_id}')
    def edit_writing_memory(item_id: str, payload: WritingMemoryInput) -> dict[str, object]:
        """Editing an approved fact reverts it to proposal so it must be approved again."""
        ensure_tables()
        with connection_factory() as conn:
            row = conn.execute('SELECT id FROM writing_memory_items WHERE id=?', (item_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='No se encontró la ficha de memoria.')
            conn.execute(
                'UPDATE writing_memory_items SET kind=?,title=?,content=?,keywords=?,source_ref=?,status=\'proposed\',updated_at=? WHERE id=?',
                (payload.kind, payload.title, payload.content, payload.keywords, payload.source_ref, _now(), item_id),
            )
            updated = conn.execute('SELECT * FROM writing_memory_items WHERE id=?', (item_id,)).fetchone()
            return dict(updated)

    @app.post('/api/writing/memory/{item_id}/status')
    def update_writing_memory_status(item_id: str, payload: WritingMemoryStatusInput) -> dict[str, object]:
        ensure_tables()
        with connection_factory() as conn:
            row = conn.execute('SELECT * FROM writing_memory_items WHERE id=?', (item_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='No se encontró la ficha de memoria.')
            conn.execute(
                'UPDATE writing_memory_items SET status=?, updated_at=? WHERE id=?',
                (payload.status, _now(), item_id),
            )
            updated = conn.execute('SELECT * FROM writing_memory_items WHERE id=?', (item_id,)).fetchone()
            return dict(updated)

    @app.get('/api/writing/projects/{project_id}/chapters')
    def list_writing_chapters(project_id: str) -> list[dict[str, object]]:
        ensure_tables()
        with connection_factory() as conn:
            require_project(conn, project_id)
            rows = conn.execute(
                'SELECT id, project_id, chapter_number, title, status, current_version, created_at, updated_at '
                'FROM writing_chapters WHERE project_id=? ORDER BY chapter_number',
                (project_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    @app.post('/api/writing/projects/{project_id}/chapters')
    def create_writing_chapter(project_id: str, payload: WritingChapterInput) -> dict[str, object]:
        ensure_tables()
        now = _now()
        chapter_id = str(uuid4())
        with connection_factory() as conn:
            require_project(conn, project_id)
            number = payload.chapter_number
            if number is None:
                row = conn.execute(
                    'SELECT COALESCE(MAX(chapter_number), 0) + 1 AS next_number FROM writing_chapters WHERE project_id=?',
                    (project_id,),
                ).fetchone()
                number = int(row['next_number'])
            existing = conn.execute(
                'SELECT id FROM writing_chapters WHERE project_id=? AND chapter_number=?',
                (project_id, number),
            ).fetchone()
            if existing is not None:
                raise HTTPException(status_code=409, detail='Ese número de capítulo ya existe en este proyecto.')
            conn.execute(
                'INSERT INTO writing_chapters(id,project_id,chapter_number,title,content,status,current_version,created_at,updated_at) '
                'VALUES (?,?,?,?,?,\'draft\',1,?,?)',
                (chapter_id, project_id, number, payload.title, payload.content, now, now),
            )
            conn.execute(
                'INSERT INTO writing_chapter_versions(id,chapter_id,version_number,title,content,created_at) VALUES (?,?,?,?,?,?)',
                (str(uuid4()), chapter_id, 1, payload.title, payload.content, now),
            )
            row = conn.execute('SELECT id,project_id,chapter_number,title,content,status,current_version,created_at,updated_at FROM writing_chapters WHERE id=?', (chapter_id,)).fetchone()
            return dict(row)

    @app.get('/api/writing/chapters/{chapter_id}')
    def get_writing_chapter(chapter_id: str) -> dict[str, object]:
        ensure_tables()
        with connection_factory() as conn:
            row = conn.execute('SELECT * FROM writing_chapters WHERE id=?', (chapter_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='No se encontró el borrador.')
            return dict(row)

    @app.put('/api/writing/chapters/{chapter_id}')
    def update_writing_chapter(chapter_id: str, payload: WritingChapterEditInput) -> dict[str, object]:
        ensure_tables()
        now = _now()
        with connection_factory() as conn:
            row = conn.execute('SELECT * FROM writing_chapters WHERE id=?', (chapter_id,)).fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail='No se encontró el borrador.')
            current_version = int(row['current_version'])
            next_version = current_version + 1
            conn.execute(
                'UPDATE writing_chapters SET title=?,content=?,current_version=?,updated_at=? WHERE id=?',
                (payload.title, payload.content, next_version, now, chapter_id),
            )
            conn.execute(
                'INSERT INTO writing_chapter_versions(id,chapter_id,version_number,title,content,created_at) VALUES (?,?,?,?,?,?)',
                (str(uuid4()), chapter_id, next_version, payload.title, payload.content, now),
            )
            updated = conn.execute('SELECT * FROM writing_chapters WHERE id=?', (chapter_id,)).fetchone()
            return dict(updated)

    @app.get('/api/writing/chapters/{chapter_id}/versions')
    def list_writing_chapter_versions(chapter_id: str) -> list[dict[str, object]]:
        ensure_tables()
        with connection_factory() as conn:
            exists = conn.execute('SELECT id FROM writing_chapters WHERE id=?', (chapter_id,)).fetchone()
            if exists is None:
                raise HTTPException(status_code=404, detail='No se encontró el borrador.')
            rows = conn.execute(
                'SELECT version_number,title,content,created_at FROM writing_chapter_versions WHERE chapter_id=? ORDER BY version_number DESC',
                (chapter_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    @app.post('/api/writing/projects/{project_id}/prompt')
    def build_writing_prompt(project_id: str, payload: WritingPromptInput) -> dict[str, object]:
        ensure_tables()
        bot = None
        with connection_factory() as conn:
            project = dict(require_project(conn, project_id))
            if payload.bot_id:
                bot_row = conn.execute(
                    'SELECT * FROM writing_bots WHERE id=? AND project_id=?',
                    (payload.bot_id, project_id),
                ).fetchone()
                if bot_row is None:
                    raise HTTPException(status_code=404, detail='El bot seleccionado no pertenece a este proyecto o ya no existe.')
                bot = dict(bot_row)
            memory_rows = conn.execute(
                'SELECT id,kind,title,content,keywords,source_ref,status,created_at,updated_at '
                'FROM writing_memory_items WHERE project_id=? AND status=\'approved\'',
                (project_id,),
            ).fetchall()
            approved = [dict(row) for row in memory_rows]
        role = bot['role'] if bot else payload.role
        selected = _select_memories(approved, payload.user_instruction)
        language_label = {'es': 'español', 'en': 'inglés', 'ja': 'japonés', 'ko': 'coreano', 'other': 'el idioma configurado por el autor'}.get(project['language'], 'español')
        parts = [
            'Eres un asistente editorial dentro de NovelTrad. El usuario es el autor y conserva el control final.',
            f"Proyecto: {project['title']}",
            f"Género: {project.get('genre') or 'no especificado'}",
            f"Idioma de salida: {language_label}",
            'Guía de estilo aprobada por el autor:\n' + (project.get('style_guide') or 'No hay guía específica guardada; pide aclaración si la voz o el estilo resulta esencial.'),
            'Rol solicitado:\n' + ROLE_INSTRUCTIONS[role],
            ('Perfil de bot elegido:\nNombre: ' + bot['name'] + '\nProveedor previsto: ' + bot['provider'] + '\nInstrucciones adicionales del autor (subordinadas al canon aprobado):\n' + (bot['instructions'] or 'Sin instrucciones adicionales.')) if bot else 'Perfil de bot: preset incorporado, sin personalidad adicional guardada.',
            'Memoria interna aprobada (solo estos hechos están confirmados como canon para esta tarea):',
        ]
        if selected:
            for item in selected:
                source_ref = str(item.get('source_ref') or 'sin referencia de origen registrada')
                parts.append(f"[MEM:{item['id']}] tipo={item['kind']} título={item['title']}\nContenido: {item['content']}\nProcedencia: {source_ref}")
        else:
            parts.append('No se recuperaron fichas aprobadas para esta tarea. No inventes recuerdos del proyecto; distingue lo no establecido.')
        parts.extend([
            'Reglas permanentes: no promociones ideas nuevas a canon; no digas que una ficha o evidencia existe si no está en el contexto; si dos fichas seleccionadas se contradicen, señala CONFLICTO; conserva los nombres y términos del proyecto.',
            'Solicitud del autor:\n' + payload.user_instruction,
            'Entrega la respuesta en el idioma del proyecto salvo que el autor pida explícitamente otro formato. La respuesta es una propuesta hasta que se guarde y revise por el autor.',
        ])
        prompt = '\n\n'.join(parts)
        return {
            'project_id': project_id,
            'role': role,
            'bot': ({'id': bot['id'], 'name': bot['name'], 'provider': bot['provider']} if bot else None),
            'prompt': prompt,
            'memory_used': [
                {'id': item['id'], 'kind': item['kind'], 'title': item['title'], 'source_ref': item['source_ref']}
                for item in selected
            ],
            'memory_count': len(selected),
            'provider_submission': 'manual_only',
            'saved_automatically': False,
        }
