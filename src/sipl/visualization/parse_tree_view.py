"""Візуалізація дерева синтаксичного виводу (VIS-01): текст, JSON, DOT, SVG.

Усе генерується з реального дерева розбору (sipl.parse_tree.ParseNode); кожен вузол
пов'язаний із фрагментом вихідного тексту через SourceSpan.
"""
from __future__ import annotations

import json
from typing import Any, Iterator, Optional

from ..parse_tree import ParseNode
from ..parser import parse_tree
from ..source import SourceSpan


def walk(root: ParseNode) -> Iterator[tuple[int, ParseNode, Optional[int], int]]:
    """Обхід у прямому порядку: (id, вузол, id батька, глибина). id починаються з 1."""
    counter = 0

    def rec(node: ParseNode, parent: Optional[int], depth: int):
        nonlocal counter
        counter += 1
        my_id = counter
        yield my_id, node, parent, depth
        for child in node.children:
            yield from rec(child, my_id, depth + 1)

    yield from rec(root, None, 0)


def span_str(span: SourceSpan) -> str:
    """'рядок:колонка-рядок:колонка'; кінець не включається."""
    s, e = span.start, span.end
    return f"{s.line}:{s.column}-{e.line}:{e.column}"


def label(node: ParseNode) -> str:
    return f"{node.symbol} [{node.rule}]" if not node.terminal else node.symbol


def leaf_numbers(root: ParseNode) -> dict[int, int]:
    """id(листка) -> номер у порядку обходу зліва направо (з 1), як на рис. 1 практикуму."""
    return {id(leaf): n for n, leaf in enumerate(root.leaves(), start=1)}


def leaf_sequence(root: ParseNode) -> str:
    """'1 begin 2 R 3 := ...': програма, прочитана з листків (перевірка синтаксичної коректності)."""
    return " ".join(f"{n} {leaf.symbol}" for n, leaf in enumerate(root.leaves(), start=1))


# ---------------------------------------------------------------- текст
def to_text(root: ParseNode, with_leaves: bool = False) -> str:
    numbers = leaf_numbers(root)
    lines: list[str] = []

    def rec(node: ParseNode, prefix: str, is_last: bool, is_root: bool) -> None:
        branch = "" if is_root else ("└── " if is_last else "├── ")
        name = f"[{numbers[id(node)]}] {node.symbol}" if node.terminal else label(node)
        lines.append(f"{prefix}{branch}{name}  {span_str(node.span)}")
        child_prefix = prefix if is_root else prefix + ("    " if is_last else "│   ")
        for i, child in enumerate(node.children):
            rec(child, child_prefix, i == len(node.children) - 1, False)

    rec(root, "", True, True)
    text = "\n".join(lines) + "\n"
    if with_leaves:
        text += "\nОбхід листків зліва направо: " + leaf_sequence(root) + "\n"
    return text


# ---------------------------------------------------------------- JSON
def to_dict(root: ParseNode, source: str) -> dict[str, Any]:
    ids = {id(node): i for i, node, _, _ in walk(root)}
    numbers = leaf_numbers(root)

    def rec(node: ParseNode) -> dict[str, Any]:
        s, e = node.span.start, node.span.end
        d: dict[str, Any] = {
            "id": ids[id(node)],
            "symbol": node.symbol,
            "terminal": node.terminal,
            "rule": node.rule,
            "span": {
                "start": {"offset": s.offset, "line": s.line, "column": s.column},
                "end": {"offset": e.offset, "line": e.line, "column": e.column},
            },
            "text": node.span.text(source),
        }
        if node.terminal:
            d["order"] = numbers[id(node)]
        else:
            d["children"] = [rec(c) for c in node.children]
        return d

    return rec(root)


def to_json(root: ParseNode, source: str, indent: int | None = 2) -> str:
    return json.dumps(to_dict(root, source), ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------- DOT
def dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def to_dot(root: ParseNode, source: Optional[str] = None) -> str:
    lines = [
        "digraph SIPL_ParseTree {",
        "  graph [ordering=out, nodesep=0.25, ranksep=0.55];",
        '  node [fontname="Arial"];',
        "  edge [arrowsize=0.6];",
    ]
    edges: list[str] = []
    numbers = leaf_numbers(root)
    for i, node, parent, _ in walk(root):
        tip = span_str(node.span)
        if source is not None:
            tip = f"{node.span.text(source)} ({tip})"
        if node.terminal:
            attrs = (f'label="[{numbers[id(node)]}] {dot_escape(node.symbol)}", shape=ellipse, '
                     'style=filled, fillcolor="#fff4cc"')
        else:
            attrs = f'label="{dot_escape(node.symbol)}\\n{node.rule}", shape=box, style="rounded,filled", fillcolor="#e6f0ff"'
        lines.append(f'  n{i} [{attrs}, tooltip="{dot_escape(tip)}"];')
        if parent is not None:
            edges.append(f"  n{parent} -> n{i};")
    lines.extend(edges)
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- обгортка
class ParseTreeView:
    """Дерево виводу SIPL-програми та його подання в різних форматах."""

    def __init__(self, source: str):
        self.source = source
        self.root = parse_tree(source)          # кидає SiplSyntaxError для некоректної програми

    def node_count(self) -> int:
        return sum(1 for _ in walk(self.root))

    def to_text(self, leaves: bool = False) -> str:
        return to_text(self.root, with_leaves=leaves)

    def leaf_sequence(self) -> str:
        return leaf_sequence(self.root)

    def to_json(self, indent: int | None = 2) -> str:
        return to_json(self.root, self.source, indent)

    def to_dict(self) -> dict[str, Any]:
        return to_dict(self.root, self.source)

    def to_dot(self) -> str:
        return to_dot(self.root, self.source)

    def to_svg(self) -> str:
        from .svg import to_svg
        return to_svg(self.root, self.source)
