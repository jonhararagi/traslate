from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from noveltrad.main import home


def test_embedded_reader_javascript_parses():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed; JavaScript syntax check is optional locally.")

    match = re.search(r"<script>(.*?)</script>", home(), flags=re.DOTALL)
    assert match, "The reader page should contain its application script."
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as handle:
        handle.write(match.group(1))
        script_path = Path(handle.name)

    try:
        result = subprocess.run(
            [node, "--check", str(script_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
    finally:
        script_path.unlink(missing_ok=True)




def test_persistent_reader_has_page_navigation_zoom_and_manual_translation_handoff():
    page = home()
    for control in (
        'id="page-indicator"',
        'id="previous"',
        'id="next"',
        'id="chapter-select"',
        'id="read-page"',
        'id="translate-page"',
        'id="read-page-modal"',
        'id="read-page-larger"',
        'id="page-translation-prompt"',
        'id="page-translation-answer"',
        'id="page-save-translation"',
    ):
        assert control in page

    assert "async function goToPage(nextIndex)" in page
    assert "chapterPagePositions[String(chapterPos)]" in page
    assert "chapter_pages:chapterPagePositions" in page
    assert "/reader-pages/translations" in page
    assert "recuperar esa respuesta automáticamente desde la web" in page
    assert "function persistTranslationPages()" in page

def test_manual_narrative_assistant_exposes_consent_gated_workflow():
    page = home()
    assert "Microventana de asistencia narrativa" in page
    assert "na-consent-nt" in page
    assert "Copiar prompt autorizado" in page
    assert "https://chatgpt.com/" in page
    assert "https://gemini.google.com/app" in page
    assert "no automatiza ChatGPT/Gemini" in page
    assert "envío automático" in page.lower()
    assert "function revokeConsentOnEdit()" in page
    assert "source.addEventListener('input', revokeConsentOnEdit)" in page
    assert "context.addEventListener('input', revokeConsentOnEdit)" in page
    assert "task.addEventListener('change', revokeConsentOnEdit)" in page
    assert "function closeDialog()" in page
    assert "button.focus()" in page
    assert "if (e.key !== 'Tab') return" in page
    assert "overlay.contains(document.activeElement)" in page


def test_manual_narrative_assistant_has_no_network_or_persistence_side_channels():
    page = home()
    marker = "/* Manual narrative-assistance micro-window: no network calls or provider-session automation. */"
    assert marker in page
    assistant = page.split(marker, 1)[1].split("\n})();", 1)[0]

    # The assistant may use the clipboard and open fixed provider home pages, but
    # must not call app/API endpoints or read/write browser persistence/session APIs.
    forbidden_patterns = (
        r"\bfetch\s*\(",
        r"\bXMLHttpRequest\b",
        r"\bWebSocket\b",
        r"\bEventSource\b",
        r"\bsendBeacon\s*\(",
        r"\bpostMessage\s*\(",
        r"\blocalStorage\b",
        r"\bsessionStorage\b",
        r"\bindexedDB\b",
        r"\bdocument\.cookie\b",
        r"\bcaches\.",
        r"\bserviceWorker\b",
    )
    for pattern in forbidden_patterns:
        assert not re.search(pattern, assistant), f"Assistant must not use forbidden network/persistence API: {pattern}"

    assert "window.open(url, '_blank', 'noopener,noreferrer')" in assistant
    assert "openProvider('https://chatgpt.com/')" in assistant
    assert "openProvider('https://gemini.google.com/app')" in assistant
