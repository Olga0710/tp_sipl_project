"""Візуалізація SIPL: дерево синтаксичного виводу (VIS-01)."""
from __future__ import annotations

from pathlib import Path

from .parse_tree_view import ParseTreeView

__all__ = ["ParseTreeView", "export_parse_tree"]


def export_parse_tree(source: str, basename: str | Path) -> list[Path]:
    """Записати <basename>.txt/.json/.dot/.svg (UTF-8). Повертає шляхи створених файлів."""
    view = ParseTreeView(source)
    base = Path(basename)
    base.parent.mkdir(parents=True, exist_ok=True)
    outputs = {
        ".txt": view.to_text(),
        ".json": view.to_json(),
        ".dot": view.to_dot(),
        ".svg": view.to_svg(),
    }
    written = []
    for suffix, content in outputs.items():
        path = base.with_suffix(suffix)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
