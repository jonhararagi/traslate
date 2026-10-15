from __future__ import annotations

import os
import sqlite3
import tempfile
from contextlib import contextmanager
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


class GlossaryInput(BaseModel):
    source_term: str = Field(min_length=1, max_length=300)
    preferred_term: str = Field(min_length=1, max_length=300)
    rule: str = Field(pattern="^(preserve|translate|contextual|protect)$")
    notes: str = Field(default="", max_length=2000)
    approved: bool = False


app = FastAPI(title=APP_NAME, version="0.1.0", docs_url="/api/docs")


@app.on_event("startup")
def startup() -> None:
    init_db()


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


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return '''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NovelTrad — Tu biblioteca</title><style>
:root{color-scheme:light dark;--bg:#f5f0e8;--panel:#fffdf8;--ink:#28251f;--muted:#777064;--accent:#6b5a9e;--line:#e4ddd1}
@media(prefers-color-scheme:dark){:root{--bg:#191a20;--panel:#23252d;--ink:#ece9e2;--muted:#aaa6b0;--accent:#c0b2ff;--line:#393b46}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:960px;margin:auto;padding:32px 20px 64px}.top{display:flex;align-items:center;gap:12px;margin-bottom:28px}.mark{background:var(--accent);color:white;border-radius:14px;padding:9px 12px;font-weight:800}.sub{color:var(--muted)}h1{font-size:clamp(1.8rem,5vw,2.6rem);line-height:1.15;margin:.2rem 0}.panel{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:22px;margin:18px 0;box-shadow:0 6px 24px #00000008}button,.file{display:inline-flex;align-items:center;justify-content:center;background:var(--accent);color:white;border:0;border-radius:12px;padding:11px 16px;font:inherit;font-weight:650;cursor:pointer}input[type=file]{max-width:100%;margin:12px 0}button:focus-visible,input:focus-visible{outline:3px solid var(--accent);outline-offset:3px}.book{padding:14px 0;border-bottom:1px solid var(--line)}.book:last-child{border:0}.empty{padding:24px;text-align:center;color:var(--muted)}#status{margin-top:12px;min-height:1.5em}.pill{font-size:.8rem;border:1px solid var(--line);border-radius:99px;padding:3px 9px;color:var(--muted)}</style></head>
<body><main><header class="top"><div class="mark">NT</div><div><strong>NovelTrad</strong><div class="sub">Tu biblioteca, tus reglas, tu espacio</div></div><span style="margin-left:auto" class="pill">Local-first</span></header>
<h1>Volvé a tu historia.</h1><p class="sub">Un lector tranquilo para tus novelas, con memoria de traducción propia. Tus libros se guardan en este equipo.</p>
<section class="panel"><h2>Importar una novela</h2><p class="sub">Solo EPUB y PDF · Máximo 100 MB por archivo. Los PDF escaneados todavía necesitan OCR.</p><form id="upload"><input id="file" name="file" type="file" accept=".epub,.pdf,application/pdf,application/epub+zip" required><br><button type="submit">Añadir a mi biblioteca</button></form><div id="status" role="status" aria-live="polite"></div></section>
<section class="panel"><h2>Mi biblioteca</h2><div id="books" class="empty">Cargando biblioteca…</div></section>
<p class="sub" style="font-size:.9rem">Esta primera base incluye biblioteca, importación y memoria terminológica. La traducción automática y el lector completo se incorporarán en fases posteriores.</p></main>
<script>
const statusEl=document.querySelector('#status'), booksEl=document.querySelector('#books');
async function refresh(){try{const r=await fetch('/api/books');if(!r.ok)throw new Error('No se pudo leer la biblioteca');const books=await r.json();booksEl.className=books.length?'':'empty';booksEl.innerHTML=books.length?books.map(b=>`<article class="book"><strong>${escapeHtml(b.title)}</strong><div class="sub">${b.chapter_count} secciones · ${b.source_format.toUpperCase()} · Importado</div></article>`).join(''):'Todavía no hay novelas. Importá un EPUB o PDF para empezar.'}catch(e){booksEl.textContent=e.message}}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
document.querySelector('#upload').addEventListener('submit',async e=>{e.preventDefault();const file=document.querySelector('#file').files[0];if(!file)return;statusEl.textContent='Importando y preparando el libro…';const data=new FormData();data.append('file',file);try{const r=await fetch('/api/books/import',{method:'POST',body:data});const result=await r.json();if(!r.ok)throw new Error(result.detail||'No se pudo importar el archivo');statusEl.textContent=`“${result.title}” se importó correctamente (${result.chapter_count} secciones).`;e.target.reset();await refresh()}catch(err){statusEl.textContent=err.message}});refresh();
</script></body></html>'''


def run() -> None:
    import uvicorn
    uvicorn.run("noveltrad.main:app", host="127.0.0.1", port=8765, reload=False)


if __name__ == "__main__":
    run()
