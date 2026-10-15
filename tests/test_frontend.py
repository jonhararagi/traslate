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
