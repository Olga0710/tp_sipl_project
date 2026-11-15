#!/usr/bin/env python3
"""Перевірка релізного тегу та витяг приміток з CHANGELOG.md (REL-02).

Використання:  python scripts/release_notes.py v0.5.0 [--out release_notes.md]

Перевіряє, що тег має вигляд vMAJOR.MINOR.PATCH (SemVer), що версія збігається
з pyproject.toml та sipl/__init__.py, і що в CHANGELOG.md є непорожній розділ цієї версії.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")


class ReleaseError(Exception):
    pass


def _read(root: Path, name: str) -> str:
    path = root / name
    if not path.exists():
        raise ReleaseError(f"Не знайдено файл {name}")
    return path.read_text(encoding="utf-8")


def project_version(root: Path) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', _read(root, "pyproject.toml"), re.MULTILINE)
    if not match:
        raise ReleaseError("У pyproject.toml не знайдено version")
    return match.group(1)


def package_version(root: Path) -> str:
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', _read(root, "src/sipl/__init__.py"), re.MULTILINE)
    if not match:
        raise ReleaseError("У src/sipl/__init__.py не знайдено __version__")
    return match.group(1)


def changelog_section(root: Path, version: str) -> str:
    out: list[str] = []
    inside = False
    for line in _read(root, "CHANGELOG.md").splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = re.match(rf"## \[{re.escape(version)}\]", line) is not None
            continue
        if inside:
            if re.match(r"^\[[^\]]+\]:", line):       # посилання внизу файлу
                break
            out.append(line)
    return "\n".join(out).strip()


def check_release(tag: str, root: Path) -> str:
    """Повертає примітки до релізу або кидає ReleaseError."""
    match = TAG_RE.match(tag)
    if not match:
        raise ReleaseError(f"Тег '{tag}' не відповідає SemVer: очікується vMAJOR.MINOR.PATCH, наприклад v0.5.0")
    version = match.group(1)
    for label, found in (("pyproject.toml", project_version(root)), ("sipl/__init__.py", package_version(root))):
        if found != version:
            raise ReleaseError(f"Версія в {label} ({found}) не збігається з тегом ({version})")
    notes = changelog_section(root, version)
    if not notes:
        raise ReleaseError(f"У CHANGELOG.md немає розділу '## [{version}]' або він порожній")
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="назва тегу, наприклад v0.5.0")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--out", type=Path, help="куди записати примітки до релізу")
    args = parser.parse_args(argv)
    try:
        notes = check_release(args.tag, args.root)
    except ReleaseError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    if args.out:
        args.out.write_text(notes + "\n", encoding="utf-8")
    else:
        print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
