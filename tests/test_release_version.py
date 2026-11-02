"""Exercise the release gate against the versions in tagged source."""

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_release_version.py"


@pytest.mark.parametrize(
    ("tag", "project_version", "api_version", "expected"),
    [
        ("v2.7.1", "2.7.1", "2.7.1", 0),
        ("v2.7.1", "2.6.1", "2.7.1", 1),
        ("v2.7.1", "2.7.1", "2.5.4", 1),
        ("2.7.1", "2.7.1", "2.7.1", 2),
    ],
)
def test_release_version_gate(tmp_path, tag, project_version, api_version, expected):
    project_file = tmp_path / "pyproject.toml"
    project_file.write_text(
        f'[project]\nversion = "{project_version}"\n', encoding="utf-8"
    )
    state_file = tmp_path / "_state.py"
    state_file.write_text(f'API_VERSION = "{api_version}"\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), tag, str(project_file), str(state_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == expected
    if expected == 1:
        assert "does not match" in result.stderr


def test_repository_versions_match():
    project_file = ROOT / "pyproject.toml"
    with project_file.open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            f"v{version}",
            str(project_file),
            str(ROOT / "src" / "api" / "v1" / "_state.py"),
        ],
        check=True,
    )
