"""Подання AST: словник (для JSON), текст, а також простий аналіз змінних."""
from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, cast

from . import ast
from .source import SourceSpan


def _fields(node: ast.Node):
    """Поля dataclass-вузла AST (базовий клас Node сам не є dataclass)."""
    return fields(cast(Any, node))


def _span_dict(span: SourceSpan) -> dict[str, Any]:
    return asdict(span)


def _span_str(span: SourceSpan) -> str:
    s, e = span.start, span.end
    return f"{s.line}:{s.column}-{e.line}:{e.column}"


def ast_to_dict(node: ast.Node, *, spans: bool = True) -> dict[str, Any]:
    """AST -> вкладений словник: {'node': 'Assign', 'target': 'x', 'value': {...}, 'span': {...}}."""
    result: dict[str, Any] = {"node": type(node).__name__}
    for f in _fields(node):
        if f.name == "span":
            continue
        value = getattr(node, f.name)
        result[f.name] = ast_to_dict(value, spans=spans) if isinstance(value, ast.Node) else value
    if spans and node.span is not None:
        result["span"] = _span_dict(node.span)
    return result


def _details(node: ast.Node) -> str:
    if isinstance(node, ast.Num):
        return str(node.value)
    if isinstance(node, ast.Var):
        return node.name
    if isinstance(node, (ast.BinOp, ast.Compare)):
        return node.op
    if isinstance(node, ast.Assign):
        return f"{node.target} :="
    return ""


def ast_to_text(root: ast.Node) -> str:
    lines: list[str] = []

    def rec(node: ast.Node, prefix: str, is_last: bool, is_root: bool, field_name: str) -> None:
        branch = "" if is_root else ("└── " if is_last else "├── ")
        head = f"{field_name}: " if field_name else ""
        detail = f" {_details(node)}" if _details(node) else ""
        span = f"  {_span_str(node.span)}" if node.span is not None else ""
        lines.append(f"{prefix}{branch}{head}{type(node).__name__}{detail}{span}")
        kids = [(f.name, getattr(node, f.name)) for f in _fields(node)
                if isinstance(getattr(node, f.name), ast.Node)]
        child_prefix = prefix if is_root else prefix + ("    " if is_last else "│   ")
        for i, (name, kid) in enumerate(kids):
            rec(kid, child_prefix, i == len(kids) - 1, False, name)

    rec(root, "", True, True, "")
    return "\n".join(lines) + "\n"


def variables(root: ast.Node) -> tuple[set[str], set[str]]:
    """(прочитані змінні, присвоєні змінні). Прочитані, але ніколи не присвоєні — вхідні."""
    read: set[str] = set()
    assigned: set[str] = set()

    def rec(node: ast.Node) -> None:
        if isinstance(node, ast.Var):
            read.add(node.name)
        elif isinstance(node, ast.Assign):
            assigned.add(node.target)
        for f in _fields(node):
            value = getattr(node, f.name)
            if isinstance(value, ast.Node):
                rec(value)

    rec(root)
    return read, assigned


def input_variables(root: ast.Node) -> list[str]:
    """Вхідні змінні: ті, що можуть бути прочитані раніше, ніж їм гарантовано присвоєно значення.

    Їх треба задати через --set. Аналіз простий і консервативний ("визначене присвоювання"):
    після if значення гарантовано лише для змінних, присвоєних в обох гілках;
    після while — лише ті, що були визначені до циклу (тіло може не виконатись).
    """
    inputs: set[str] = set()

    def need(node: ast.Node, defined: frozenset[str]) -> None:
        inputs.update(variables(node)[0] - defined)

    def stmt(node: ast.Node, defined: frozenset[str]) -> frozenset[str]:
        if isinstance(node, ast.Program):
            return stmt(node.body, defined)
        if isinstance(node, ast.Assign):
            need(node.value, defined)
            return defined | {node.target}
        if isinstance(node, ast.Seq):
            return stmt(node.second, stmt(node.first, defined))
        if isinstance(node, ast.Block):
            return stmt(node.body, defined)
        if isinstance(node, ast.If):
            need(node.cond, defined)
            return stmt(node.then, defined) & stmt(node.orelse, defined)
        if isinstance(node, ast.While):
            need(node.cond, defined)
            stmt(node.body, defined)
            return defined
        return defined                                         # Skip

    stmt(root, frozenset())
    return sorted(inputs)
