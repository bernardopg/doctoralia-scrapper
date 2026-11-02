#!/usr/bin/env python3
"""Ensure a release tag matches the version declared in its source tree."""

import sys
import tomllib
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3 or not sys.argv[1].startswith("v"):
        print(
            "Usage: verify_release_version.py vVERSION pyproject.toml", file=sys.stderr
        )
        return 2

    tag, project_file = sys.argv[1:]
    with Path(project_file).open("rb") as stream:
        version = tomllib.load(stream)["project"]["version"]
    if version != tag[1:]:
        print(
            f"Release tag {tag} does not match project version {version}. "
            "Update pyproject.toml before creating the release tag.",
            file=sys.stderr,
        )
        return 1

    print(f"Release tag {tag} matches project version {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
