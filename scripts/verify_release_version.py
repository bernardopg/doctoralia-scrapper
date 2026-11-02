#!/usr/bin/env python3
"""Ensure a release tag matches versions declared in its source tree."""

import ast
import sys
import tomllib
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4 or not sys.argv[1].startswith("v"):
        print(
            "Usage: verify_release_version.py vVERSION pyproject.toml _state.py",
            file=sys.stderr,
        )
        return 2

    tag, project_file, state_file = sys.argv[1:]
    with Path(project_file).open("rb") as stream:
        project_version = tomllib.load(stream)["project"]["version"]
    tree = ast.parse(Path(state_file).read_text(encoding="utf-8"))
    api_versions = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "API_VERSION"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if project_version != tag[1:] or api_versions != [tag[1:]]:
        print(
            f"Release tag {tag} does not match project version {project_version} "
            f"and API version {api_versions}. Update both before tagging.",
            file=sys.stderr,
        )
        return 1

    print(f"Release tag {tag} matches project and API versions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
