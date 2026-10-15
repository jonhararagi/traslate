"""Windows launcher for the packaged NovelTrad local web application."""
from __future__ import annotations

import threading
import webbrowser

import uvicorn
from noveltrad.main import app


def main() -> None:
    url = "http://127.0.0.1:8765"
    # Open the browser only for this desktop launcher; the console entry point
    # keeps its existing behavior and never opens a tab implicitly.
    threading.Timer(1.5, lambda: webbrowser.open(url, new=2)).start()
    uvicorn.run(app, host="127.0.0.1", port=8765, reload=False, log_level="warning")


if __name__ == "__main__":
    main()
