"""Windows launcher for the packaged NovelTrad local web application.

The packaged, windowed executable has no visible console. Write startup failures
to a local log and show a concise Windows dialog so an import/packaging error
does not collapse into PyInstaller's generic "Unhandled exception in script".
"""
from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path


def _configure_startup_logging() -> Path | None:
    """Create a small diagnostic log before importing application dependencies."""
    override = os.environ.get("NOVELTRAD_STARTUP_LOG", "").strip()
    if override:
        candidates = [Path(override).expanduser()]
    elif os.name == "nt":
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        candidates = [local_app_data / "NovelTrad" / "logs" / "startup.log"]
    else:
        state_home = Path(
            os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")
        )
        candidates = [state_home / "noveltrad" / "logs" / "startup.log"]

    candidates.append(Path(tempfile.gettempdir()) / "noveltrad-startup.log")
    seen: set[str] = set()
    for path in candidates:
        normalized = str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(path, encoding="utf-8")
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                handlers=[handler],
                force=True,
            )
            return path
        except OSError:
            continue

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    return None


def _open_browser(url: str) -> None:
    try:
        if not webbrowser.open(url, new=2):
            logging.warning("The default browser did not open %s automatically.", url)
    except Exception:
        logging.exception("Could not open the browser automatically.")


def _show_startup_error(message: str) -> None:
    """Report errors without forcing a dialog in automated CI smoke tests."""
    if os.environ.get("NOVELTRAD_NO_ERROR_DIALOG") == "1":
        logging.error("Startup dialog suppressed by NOVELTRAD_NO_ERROR_DIALOG.")
        return

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                None, message, "NovelTrad — Error de inicio", 0x10
            )
            return
        except Exception:
            logging.exception("Could not show the Windows startup-error dialog.")

    try:
        print(message, file=sys.stderr)
    except Exception:
        logging.exception("Could not print the startup error message.")


def main() -> None:
    log_path = _configure_startup_logging()
    logging.info("NovelTrad desktop launcher starting.")
    try:
        # Import inside the guarded block: missing frozen modules/DLLs can fail
        # before the old launcher reached main(), leaving only a generic dialog.
        import uvicorn
        from noveltrad.main import app

        url = "http://127.0.0.1:8765"
        if os.environ.get("NOVELTRAD_NO_BROWSER") != "1":
            # Open a browser only for this desktop launcher; the console entry
            # point keeps its existing behavior and never opens a tab implicitly.
            timer = threading.Timer(1.5, _open_browser, args=(url,))
            timer.daemon = True
            timer.start()

        logging.info("Starting the local server at %s.", url)
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8765,
            reload=False,
            log_level="warning",
            # PyInstaller --windowed sets sys.stderr to None. Uvicorn's default
            # logging config installs a stderr color formatter that calls
            # isatty(), which crashes before the ASGI server can start.
            # The launcher already configured a persistent file logger above.
            log_config=None,
        )
    except Exception as exc:
        logging.exception("NovelTrad failed during startup or server launch.")
        error_details = f"{type(exc).__name__}: {exc}".strip()
        if len(error_details) > 1200:
            error_details = error_details[:1197] + "..."
        log_location = str(log_path) if log_path else "no se pudo crear un archivo de registro"
        _show_startup_error(
            "NovelTrad no pudo iniciar.\n\n"
            f"Error: {error_details}\n\n"
            f"Registro técnico: {log_location}\n\n"
            "Conservá este registro para diagnosticar el problema."
        )
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
