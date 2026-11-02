"""Exercise the release gate against the version in the tagged source."""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_release_version.py"


@pytest.mark.parametrize(
    ("tag", "version", "expected"),
    [("v2.7.0", "2.7.0", 0), ("v2.7.0", "2.6.1", 1), ("2.7.0", "2.7.0", 2)],
)
def test_release_version_gate(tmp_path, tag, version, expected):
    project_file = tmp_path / "pyproject.toml"
    project_file.write_text(f'[project]\nversion = "{version}"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), tag, str(project_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected
    if expected == 1:
        assert "does not match" in result.stderr
