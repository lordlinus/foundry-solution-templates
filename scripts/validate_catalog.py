"""Validate solution-template-catalog.json the way the Foundry Toolkit extension does.

Mirrors the checks in the Foundry Toolkit VS Code extension (1.6.20), then adds repository checks the
extension can only find at download time: the template folder and README exist, and it has no symlinks.
Run: python scripts/validate_catalog.py
"""

import json
import re
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REPO = re.compile(r"^https://github[.]com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/?$")
REQUIRED = ("id", "title", "description", "repo", "githubUrl", "ref", "path")


def safe_relative(path: str) -> bool:
    if not path or PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute():
        return False
    return all(part not in ("", ".", "..") for part in path.replace("\\", "/").split("/"))


def validate(catalog: dict) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for i, t in enumerate(catalog.get("templates", [])):
        where = f"templates[{i}]"
        for field in REQUIRED:
            if not isinstance(t.get(field), str) or not t[field].strip():
                errors.append(f"{where}.{field} is missing or empty.")
        if errors:
            continue
        if not ID.match(t["id"]) or t["id"] in seen:
            errors.append(f"{where}: invalid or duplicate id {t['id']!r}.")
        seen.add(t["id"])
        if not REPO.match(t["repo"]) or not t["githubUrl"].startswith(t["repo"].rstrip("/") + "/tree/"):
            errors.append(f"{t['id']}: repo/githubUrl invalid.")
        if not safe_relative(t["path"]):
            errors.append(f"{t['id']}: unsafe path.")
        if "readmePath" in t and not safe_relative(t["readmePath"]):
            errors.append(f"{t['id']}: unsafe readmePath.")
        tags = t.get("tags", [])
        if not isinstance(tags, list) or any(not isinstance(x, str) or not x.strip() for x in tags):
            errors.append(f"{t['id']}: tags must be non-empty strings.")
        # Repository checks for entries that point at this repository.
        if t["repo"].rstrip("/").endswith("/foundry-solution-templates"):
            folder = ROOT / t["path"]
            if not folder.is_dir():
                errors.append(f"{t['id']}: folder {t['path']} does not exist.")
                continue
            if not (folder / t.get("readmePath", "README.md")).is_file():
                errors.append(f"{t['id']}: README not found.")
            links = [p for p in folder.rglob("*") if p.is_symlink()]
            if links:
                errors.append(f"{t['id']}: symlinks are not supported by the extension: {links[:3]}.")
            if not t["githubUrl"].endswith(f"/tree/{t['ref']}/{t['path']}"):
                errors.append(f"{t['id']}: githubUrl should end with /tree/{t['ref']}/{t['path']}.")
    return errors


if __name__ == "__main__":
    problems = validate(json.loads((ROOT / "solution-template-catalog.json").read_text()))
    for p in problems:
        print(f"ERROR: {p}")
    print("catalog OK" if not problems else f"{len(problems)} problem(s)")
    sys.exit(1 if problems else 0)
