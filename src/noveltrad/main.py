from __future__ import annotations

import json
import os
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import fitz
from bs4 import BeautifulSoup
from ebooklib import epub, ITEM_DOCUMENT
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

APP_NAME = "NovelTrad"
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
ALLOWED_SUFFIXES = {".epub", ".pdf"}


def data_dir() -> Path:
    """Return a per-user data directory; tests can override NOVELTRAD_HOME."""
    override = os.environ.get("NOVELTRAD_HOME")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP_NAME
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "noveltrad"
    root.mkdir(parents=True, exist_ok=True)
    return root


def database_path() -> Path:
    return data_dir() / "noveltrad.sqlite3"


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(database_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_format TEXT NOT NULL CHECK(source_format IN ('epub', 'pdf')),
                source_name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_language TEXT NOT NULL DEFAULT 'und',
                target_language TEXT NOT NULL DEFAULT 'es',
                current_location TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_index INTEGER NOT NULL,
                title TEXT NOT NULL,
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'imported',
                UNIQUE(book_id, chapter_index)
            );
            CREATE TABLE IF NOT EXISTS glossary_entries (
                id TEXT PRIMARY KEY,
                book_id TEXT REFERENCES books(id) ON DELETE CASCADE,
                source_term TEXT NOT NULL,
                preferred_term TEXT NOT NULL,
                rule TEXT NOT NULL CHECK(rule IN ('preserve', 'translate', 'contextual', 'protect')),
                notes TEXT NOT NULL DEFAULT '',
                approved INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS translation_versions (
                id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
                version_number INTEGER NOT NULL,
                translated_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(chapter_id, version_number)
            );
            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                chapter_id TEXT REFERENCES chapters(id) ON DELETE CASCADE,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                scope TEXT NOT NULL CHECK(scope IN ('segment', 'book', 'global')),
                created_at TEXT NOT NULL
            );
            """
        )


def extract_pdf(path: Path) -> list[tuple[str, str]]:
    chapters: list[tuple[str, str]] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                chapters.append((f"Página {index}", text))
    if not chapters:
        raise ValueError("El PDF no contiene texto seleccionable. El OCR todavía no está disponible en esta versión.")
    return chapters


def extract_epub(path: Path) -> list[tuple[str, str]]:
    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    chapters: list[tuple[str, str]] = []
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        for node in soup(["script", "style", "nav"]):
            node.decompose()
        text = "\n\n".join(part.strip() for part in soup.stripped_strings if part.strip())
        if not text:
            continue
        heading = soup.find(["h1", "h2", "h3"])
        title = heading.get_text(" ", strip=True) if heading else Path(item.get_name()).stem
        chapters.append((title or f"Capítulo {len(chapters) + 1}", text))
    if not chapters:
        raise ValueError("No se encontraron capítulos con texto en este EPUB.")
    return chapters


class ProgressInput(BaseModel):
    chapter_index: int = Field(ge=0)
    scroll_top: float = Field(default=0, ge=0, le=100000000)


class TranslationInput(BaseModel):
    translated_text: str = Field(max_length=2_000_000)


class GlossaryInput(BaseModel):
    source_term: str = Field(min_length=1, max_length=300)
    preferred_term: str = Field(min_length=1, max_length=300)
    rule: str = Field(pattern="^(preserve|translate|contextual|protect)$")
    notes: str = Field(default="", max_length=2000)
    approved: bool = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=APP_NAME, version="0.1.0", docs_url="/api/docs", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"app": APP_NAME, "status": "ok", "mode": "local-first", "translation_engine": "not-configured"}


@app.get("/api/books")
def list_books() -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        rows = conn.execute(
            "SELECT b.*, COUNT(c.id) AS chapter_count FROM books b "
            "LEFT JOIN chapters c ON c.book_id = b.id GROUP BY b.id ORDER BY b.created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/books/import")
async def import_book(file: UploadFile = File(...)) -> dict[str, object]:
    init_db()
    filename = Path(file.filename or "book").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Solo se admiten archivos EPUB y PDF.")
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="El archivo está vacío.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="El límite de importación es 100 MB por archivo.")

    book_id = str(uuid4())
    safe_name = f"{book_id}{suffix}"
    source_path = data_dir() / "imports" / safe_name
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(raw)
    try:
        chapters = extract_epub(source_path) if suffix == ".epub" else extract_pdf(source_path)
    except Exception as exc:
        source_path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail="No se pudo leer el archivo. Comprueba que no esté dañado o protegido.") from exc

    title = Path(filename).stem
    now = datetime.now(timezone.utc).isoformat()
    try:
        with connection() as conn:
            conn.execute(
                "INSERT INTO books(id,title,source_format,source_name,source_path,created_at) VALUES(?,?,?,?,?,?)",
                (book_id, title, suffix[1:], filename, str(source_path), now),
            )
            conn.executemany(
                "INSERT INTO chapters(id,book_id,chapter_index,title,original_text) VALUES(?,?,?,?,?)",
                [(str(uuid4()), book_id, index, chapter_title, text) for index, (chapter_title, text) in enumerate(chapters)],
            )
    except Exception:
        source_path.unlink(missing_ok=True)
        raise
    return {"id": book_id, "title": title, "format": suffix[1:], "chapter_count": len(chapters), "status": "imported"}


@app.get("/api/books/{book_id}/chapters")
def list_chapters(book_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        exists = conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        rows = conn.execute(
            "SELECT id, book_id, chapter_index, title, original_text, translated_text, status "
            "FROM chapters WHERE book_id = ? ORDER BY chapter_index", (book_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/books/{book_id}/glossary")
def list_glossary(book_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        rows = conn.execute(
            "SELECT id, source_term, preferred_term, rule, notes, approved FROM glossary_entries "
            "WHERE book_id = ? OR book_id IS NULL ORDER BY source_term COLLATE NOCASE", (book_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/books/{book_id}/glossary")
def add_glossary_entry(book_id: str, entry: GlossaryInput) -> dict[str, object]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        entry_id = str(uuid4())
        conn.execute(
            "INSERT INTO glossary_entries(id,book_id,source_term,preferred_term,rule,notes,approved,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (entry_id, book_id, entry.source_term.strip(), entry.preferred_term.strip(), entry.rule,
             entry.notes.strip(), int(entry.approved), datetime.now(timezone.utc).isoformat()),
        )
    return {"id": entry_id, **entry.model_dump()}


@app.put("/api/books/{book_id}/progress")
def save_progress(book_id: str, progress: ProgressInput) -> dict[str, object]:
    init_db()
    with connection() as conn:
        book = conn.execute("SELECT id FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            raise HTTPException(status_code=404, detail="No se encontró la novela.")
        chapter = conn.execute(
            "SELECT 1 FROM chapters WHERE book_id = ? AND chapter_index = ?",
            (book_id, progress.chapter_index),
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=422, detail="El capítulo indicado no existe en esta novela.")
        location = json.dumps(
            {"chapter_index": progress.chapter_index, "scroll_top": progress.scroll_top},
            separators=(",", ":"),
        )
        conn.execute("UPDATE books SET current_location = ? WHERE id = ?", (location, book_id))
    return {"book_id": book_id, **progress.model_dump(), "saved": True}


@app.put("/api/chapters/{chapter_id}/translation")
def save_translation(chapter_id: str, translation: TranslationInput) -> dict[str, object]:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        chapter = conn.execute(
            "SELECT id, translated_text FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        current = chapter["translated_text"]
        if current != translation.translated_text:
            version = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version "
                "FROM translation_versions WHERE chapter_id = ?", (chapter_id,)
            ).fetchone()["next_version"]
            conn.execute(
                "INSERT INTO translation_versions(id, chapter_id, version_number, translated_text, created_at) "
                "VALUES(?,?,?,?,?)",
                (str(uuid4()), chapter_id, version, current, now),
            )
            conn.execute(
                "UPDATE chapters SET translated_text = ?, status = ? WHERE id = ?",
                (translation.translated_text, "translated" if translation.translated_text.strip() else "imported", chapter_id),
            )
        return {"chapter_id": chapter_id, "translated_text": translation.translated_text, "saved": True}


@app.get("/api/chapters/{chapter_id}/translation/versions")
def translation_versions(chapter_id: str) -> list[dict[str, object]]:
    init_db()
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM chapters WHERE id = ?", (chapter_id,)).fetchone():
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        rows = conn.execute(
            "SELECT version_number, translated_text, created_at FROM translation_versions "
            "WHERE chapter_id = ? ORDER BY version_number DESC", (chapter_id,)
        ).fetchall()
        return [dict(row) for row in rows]


@app.post("/api/chapters/{chapter_id}/translation/restore/{version_number}")
def restore_translation_version(chapter_id: str, version_number: int) -> dict[str, object]:
    init_db()
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        chapter = conn.execute(
            "SELECT id, translated_text FROM chapters WHERE id = ?", (chapter_id,)
        ).fetchone()
        if not chapter:
            raise HTTPException(status_code=404, detail="No se encontró el capítulo.")
        target = conn.execute(
            "SELECT translated_text FROM translation_versions WHERE chapter_id = ? AND version_number = ?",
            (chapter_id, version_number),
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="No se encontró esa versión de la traducción.")
        next_version = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version "
            "FROM translation_versions WHERE chapter_id = ?", (chapter_id,)
        ).fetchone()["next_version"]
        conn.execute(
            "INSERT INTO translation_versions(id, chapter_id, version_number, translated_text, created_at) "
            "VALUES(?,?,?,?,?)",
            (str(uuid4()), chapter_id, next_version, chapter["translated_text"], now),
        )
        restored = target["translated_text"]
        conn.execute(
            "UPDATE chapters SET translated_text = ?, status = ? WHERE id = ?",
            (restored, "translated" if restored.strip() else "imported", chapter_id),
        )
    return {"chapter_id": chapter_id, "version_number": version_number, "translated_text": restored, "restored": True}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NovelTrad — Tu biblioteca</title><style>
:root{color-scheme:light dark;--bg:#f5f0e8;--panel:#fffdf8;--ink:#28251f;--muted:#777064;--accent:#6b5a9e;--line:#e4ddd1;--soft:#eee8f8}
@media(prefers-color-scheme:dark){:root{--bg:#191a20;--panel:#23252d;--ink:#ece9e2;--muted:#aaa6b0;--accent:#c0b2ff;--line:#393b46;--soft:#34303f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}button,input,textarea{font:inherit}button{cursor:pointer}button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid var(--accent);outline-offset:3px}main{max-width:1120px;margin:auto;padding:24px 20px 60px}.top{display:flex;align-items:center;gap:12px;margin-bottom:28px}.mark{background:var(--accent);color:white;border-radius:14px;padding:9px 12px;font-weight:800}.sub{color:var(--muted)}h1{font-size:clamp(1.8rem,5vw,2.6rem);line-height:1.15;margin:.2rem 0}h2{margin-top:0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 6px 24px #00000008}.primary,.secondary,.quiet{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:12px;padding:10px 15px;font-weight:650}.primary{background:var(--accent);color:white}.secondary{background:var(--soft);color:var(--ink)}.quiet{background:transparent;color:var(--ink);border:1px solid var(--line)}input[type=file]{max-width:100%;margin:12px 0}.book{display:flex;align-items:center;gap:16px;padding:16px 0;border-bottom:1px solid var(--line)}.book:last-child{border:0}.bookinfo{flex:1;min-width:0}.empty{padding:24px;text-align:center;color:var(--muted)}#status{margin-top:12px;min-height:1.5em}.pill{font-size:.8rem;border:1px solid var(--line);border-radius:99px;padding:3px 9px;color:var(--muted)}#reader{display:none}.reader-head{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:16px}.reader-head h2{margin:0;flex:1}.reader-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.reader-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.reading-pane{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px}.reading-pane h3{margin-top:0}.original-text{white-space:pre-wrap;overflow-wrap:anywhere;max-height:65vh;overflow:auto;font-family:Georgia,'Times New Roman',serif;line-height:1.85;font-size:19px}.translation-text{width:100%;min-height:48vh;resize:vertical;padding:12px;border:1px solid var(--line);border-radius:12px;background:var(--bg);color:var(--ink);line-height:1.85;font-family:Georgia,'Times New Roman',serif;font-size:19px}.chapter-nav{display:flex;gap:8px;align-items:center;justify-content:space-between;margin:14px 0}.chapter-nav select{max-width:65%;padding:8px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)}.reader-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}.small{font-size:.9rem}.hidden{display:none!important}@media(max-width:760px){main{padding:18px 12px 40px}.reader-grid{grid-template-columns:1fr}.original-text{max-height:45vh}.translation-text{min-height:35vh}.panel{padding:16px}.book{align-items:flex-start;flex-wrap:wrap}.bookinfo{flex-basis:60%}}
</style></head><body><main>
<header class="top"><div class="mark">NT</div><div><strong>NovelTrad</strong><div class="sub">Tu biblioteca, tus reglas, tu espacio</div></div><span style="margin-left:auto" class="pill">Local-first</span></header>
<section id="library"><h1>Volvé a tu historia.</h1><p class="sub">Un espacio tranquilo para leer y preparar tus traducciones. Tus libros se guardan en este equipo.</p>
<section class="panel"><h2>Importar una novela</h2><p class="sub">Solo EPUB y PDF · Máximo 100 MB. Los PDF escaneados todavía necesitan OCR.</p><form id="upload"><input id="file" name="file" type="file" accept=".epub,.pdf,application/pdf,application/epub+zip" required><br><button class="primary" type="submit">Añadir a mi biblioteca</button></form><div id="status" role="status" aria-live="polite"></div></section>
<section class="panel"><h2>Mi biblioteca</h2><div id="books" class="empty">Cargando biblioteca…</div></section></section>
<section id="reader"><div class="reader-head"><button id="back" class="quiet" type="button">← Biblioteca</button><h2 id="book-title">Leyendo</h2><button id="toggle-glossary" class="secondary" type="button">Glosario</button><label class="small">Texto <select id="font-size" aria-label="Tamaño del texto"><option value="17">Pequeño</option><option value="19" selected>Mediano</option><option value="22">Grande</option><option value="26">Muy grande</option></select></label></div>
<div class="chapter-nav"><button id="previous" class="secondary" type="button">← Anterior</button><select id="chapter-select" aria-label="Elegir capítulo"></select><button id="next" class="secondary" type="button">Siguiente →</button></div>
<div class="reader-grid"><section class="reading-pane"><h3>Original</h3><div id="original" class="original-text" tabindex="0"></div></section><section class="reading-pane"><h3>Traducción</h3><p class="sub small">El original permanece intacto. Tus cambios se guardan aparte.</p><textarea id="translation" class="translation-text" aria-label="Texto de traducción" placeholder="Escribí o pegá aquí tu traducción…"></textarea><div class="reader-actions"><button id="save-translation" class="primary" type="button">Guardar traducción</button><button id="show-history" class="secondary" type="button">Historial</button><span id="save-status" class="sub small" role="status" aria-live="polite"></span></div><p class="sub small">Cada guardado conserva una versión anterior.</p><div id="translation-history" class="hidden"><h4>Versiones guardadas</h4><div id="history-list"></div><p id="history-status" class="sub small" role="status" aria-live="polite"></p></div></section></div>
<section id="glossary-panel" class="panel hidden"><div class="reader-head"><h2>Glosario de esta novela</h2><button id="close-glossary" class="quiet" type="button">Cerrar</button></div><p class="sub small">Protegé nombres y fijá términos para mantener la coherencia. Las reglas se guardan por novela.</p><form id="glossary-form"><div class="reader-grid"><label>Término original<input id="glossary-source" required maxlength="300" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Oknodie"></label><label>Forma preferida<input id="glossary-target" required maxlength="300" style="display:block;width:100%;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Oknodie"></label></div><div class="reader-actions"><label>Regla <select id="glossary-rule" style="padding:9px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink)"><option value="protect">Proteger nombre/término</option><option value="preserve">Conservar exactamente</option><option value="translate">Traducir siempre así</option><option value="contextual">Depende del contexto</option></select></label><label><input id="glossary-approved" type="checkbox"> Aprobado</label><button class="primary" type="submit">Guardar término</button></div><label>Notas opcionales<textarea id="glossary-notes" rows="2" maxlength="2000" style="display:block;width:100%;margin-top:8px;padding:10px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink)" placeholder="Nombre propio; no traducir."></textarea></label><p id="glossary-status" class="sub small" role="status" aria-live="polite"></p></form><div id="glossary-list"></div></section>
</section><p class="sub small">El motor de traducción automática todavía no está configurado. Esta versión permite leer, guardar traducciones propias y retomar el progreso.</p></main>
<script>
const $=s=>document.querySelector(s);let currentBook=null,chapters=[],chapterPos=0,saveTimer=null,translationDirty=false;
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function api(url,options={}){const r=await fetch(url,options);let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.detail||'No se pudo completar la operación');return d}
async function refresh(){try{const books=await api('/api/books');$('#books').className=books.length?'':'empty';$('#books').innerHTML=books.length?books.map(b=>{let pos={};try{pos=JSON.parse(b.current_location||'{}')}catch{}return '<article class="book"><div class="bookinfo"><strong>'+esc(b.title)+'</strong><div class="sub small">'+b.chapter_count+' secciones · '+esc(b.source_format.toUpperCase())+' · Progreso guardado</div></div><button class="primary" type="button" data-open="'+esc(b.id)+'" data-chapter="'+(Number.isInteger(pos.chapter_index)?pos.chapter_index:0)+'">Abrir novela</button></article>'}).join(''):'<div class="empty">Todavía no hay novelas. Importá un EPUB o PDF para empezar.</div>'}catch(e){$('#books').textContent=e.message}}
$('#books').addEventListener('click',e=>{const b=e.target.closest('[data-open]');if(b)openBook(b.dataset.open,Number(b.dataset.chapter)||0)});
$('#upload').addEventListener('submit',async e=>{e.preventDefault();const file=$('#file').files[0];if(!file)return;$('#status').textContent='Importando y preparando el libro…';const data=new FormData();data.append('file',file);try{const result=await api('/api/books/import',{method:'POST',body:data});$('#status').textContent='“'+result.title+'” se importó correctamente ('+result.chapter_count+' secciones).';e.target.reset();await refresh()}catch(err){$('#status').textContent=err.message}});
async function openBook(id,preferred=0){try{const books=await api('/api/books');currentBook=books.find(b=>b.id===id);if(!currentBook)throw new Error('No se encontró la novela');chapters=await api('/api/books/'+id+'/chapters');if(!chapters.length)throw new Error('La novela no contiene secciones legibles');chapterPos=Math.max(0,Math.min(preferred,chapters.length-1));$('#book-title').textContent=currentBook.title;$('#chapter-select').innerHTML=chapters.map((c,i)=>'<option value="'+i+'">'+(i+1)+'. '+esc(c.title)+'</option>').join('');$('#library').classList.add('hidden');$('#reader').style.display='block';renderChapter(true)}catch(e){$('#status').textContent=e.message}}
function renderChapter(restore){const c=chapters[chapterPos];if(!c)return;translationDirty=false;$('#chapter-select').value=String(chapterPos);$('#original').textContent=c.original_text;$('#translation').value=c.translated_text||'';$('#previous').disabled=chapterPos===0;$('#next').disabled=chapterPos===chapters.length-1;$('#save-status').textContent='';$('#original').scrollTop=0;if(restore){let p={};try{p=JSON.parse(currentBook.current_location||'{}')}catch{}if(p.chapter_index===chapterPos&&Number.isFinite(p.scroll_top))$('#original').scrollTop=p.scroll_top}saveProgress()}
function goToChapter(i){if(i<0||i>=chapters.length)return;if(translationDirty&&!confirm('Hay cambios de traducción sin guardar. ¿Descartarlos y cambiar de capítulo?'))return;translationDirty=false;chapterPos=i;renderChapter(false)}
$('#chapter-select').addEventListener('change',e=>goToChapter(Number(e.target.value)));$('#previous').addEventListener('click',()=>goToChapter(chapterPos-1));$('#next').addEventListener('click',()=>goToChapter(chapterPos+1));
async function persistProgressNow(){if(!currentBook)return;clearTimeout(saveTimer);const scroll_top=$('#original').scrollTop;await api('/api/books/'+currentBook.id+'/progress',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter_index:chapterPos,scroll_top})});currentBook.current_location=JSON.stringify({chapter_index:chapterPos,scroll_top})}
function saveProgress(){if(!currentBook)return;clearTimeout(saveTimer);saveTimer=setTimeout(async()=>{try{await persistProgressNow()}catch(e){$('#save-status').textContent='No se pudo guardar el progreso: '+e.message}},250)}
$('#original').addEventListener('scroll',saveProgress);
$('#save-translation').addEventListener('click',async()=>{const c=chapters[chapterPos];$('#save-status').textContent='Guardando…';try{const result=await api('/api/chapters/'+c.id+'/translation',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({translated_text:$('#translation').value})});c.translated_text=result.translated_text;translationDirty=false;$('#save-status').textContent='Guardado en este equipo.'}catch(e){$('#save-status').textContent='Error: '+e.message}});
async function loadHistory(){const c=chapters[chapterPos];try{const versions=await api('/api/chapters/'+c.id+'/translation/versions');$('#history-list').innerHTML=versions.length?versions.map(v=>'<article class="book"><div class="bookinfo"><strong>Versión '+v.version_number+'</strong><div class="sub small">'+esc(v.created_at)+'</div><div style="white-space:pre-wrap;overflow-wrap:anywhere;margin-top:6px">'+esc(v.translated_text||'(Traducción vacía)')+'</div></div><button class="secondary" type="button" data-restore="'+v.version_number+'">Restaurar</button></article>').join(''):'<p class="empty">Todavía no hay versiones anteriores.</p>'}catch(e){$('#history-status').textContent=e.message}}
$('#show-history').addEventListener('click',async()=>{$('#translation-history').classList.toggle('hidden');if(!$('#translation-history').classList.contains('hidden'))await loadHistory()});
$('#history-list').addEventListener('click',async e=>{const button=e.target.closest('[data-restore]');if(!button)return;if(translationDirty&&!confirm('Hay cambios sin guardar. ¿Descartarlos y restaurar la versión elegida?'))return;if(!confirm('¿Restaurar esta versión? La traducción actual guardada se conservará en el historial.'))return;const c=chapters[chapterPos];$('#history-status').textContent='Restaurando…';try{const result=await api('/api/chapters/'+c.id+'/translation/restore/'+button.dataset.restore,{method:'POST'});$('#translation').value=result.translated_text;c.translated_text=result.translated_text;translationDirty=false;$('#save-status').textContent='Versión restaurada.';$('#history-status').textContent='La versión se restauró y el texto anterior quedó guardado.';await loadHistory()}catch(err){$('#history-status').textContent='Error: '+err.message}});
$('#translation').addEventListener('input',()=>{translationDirty=true;$('#save-status').textContent='Cambios sin guardar';});
window.addEventListener('beforeunload',e=>{if(translationDirty){e.preventDefault();e.returnValue=''}});
async function loadGlossary(){if(!currentBook)return;try{const entries=await api('/api/books/'+currentBook.id+'/glossary');$('#glossary-list').innerHTML=entries.length?'<div>'+entries.map(g=>'<article class="book"><div class="bookinfo"><strong>'+esc(g.source_term)+' → '+esc(g.preferred_term)+'</strong><div class="sub small">'+esc(g.rule)+' · '+(g.approved?'Aprobado':'Pendiente')+(g.notes?' · '+esc(g.notes):'')+'</div></div></article>').join('')+'</div>':'<p class="empty">Todavía no hay términos definidos para esta novela.</p>'}catch(e){$('#glossary-status').textContent=e.message}}
$('#toggle-glossary').addEventListener('click',async()=>{$('#glossary-panel').classList.remove('hidden');await loadGlossary();$('#glossary-source').focus()});
$('#close-glossary').addEventListener('click',()=>$('#glossary-panel').classList.add('hidden'));
$('#glossary-form').addEventListener('submit',async e=>{e.preventDefault();if(!currentBook)return;$('#glossary-status').textContent='Guardando término…';try{await api('/api/books/'+currentBook.id+'/glossary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_term:$('#glossary-source').value.trim(),preferred_term:$('#glossary-target').value.trim(),rule:$('#glossary-rule').value,notes:$('#glossary-notes').value.trim(),approved:$('#glossary-approved').checked})});$('#glossary-status').textContent='Término guardado.';$('#glossary-form').reset();await loadGlossary()}catch(e){$('#glossary-status').textContent='Error: '+e.message}});
$('#font-size').addEventListener('change',e=>{const size=Number(e.target.value);$('#original').style.fontSize=size+'px';$('#translation').style.fontSize=size+'px'});
$('#back').addEventListener('click',async()=>{if(translationDirty&&!confirm('Hay cambios de traducción sin guardar. ¿Salir sin guardarlos?'))return;try{await persistProgressNow()}catch(e){$('#save-status').textContent='No se pudo guardar el progreso: '+e.message;return}translationDirty=false;$('#reader').style.display='none';$('#library').classList.remove('hidden');await refresh()});
</script></body></html>'''


def run() -> None:
    import uvicorn
    uvicorn.run("noveltrad.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
