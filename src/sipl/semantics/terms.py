"""Семантичні терми програмної алгебри A_SIPL"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class Term:
    """Базовий клас семантичних термів."""


@dataclass(frozen=True)
class Const(Term):
    value: int


@dataclass(frozen=True)
class Deref(Term):
    name: str


@dataclass(frozen=True)
class Superposition(Term):
    func: str                       # add, sub, mult, eq, gr, or, neg
    args: tuple[Term, ...]

    @property
    def arity(self) -> int:
        return len(self.args)


@dataclass(frozen=True)
class AssignFn(Term):
    var: str
    expr: Term


@dataclass(frozen=True)
class Compose(Term):
    first: Term
    second: Term


@dataclass(frozen=True)
class IfFn(Term):
    cond: Term
    then: Term
    orelse: Term


@dataclass(frozen=True)
class WhileFn(Term):
    cond: Term
    body: Term


@dataclass(frozen=True)
class Identity(Term):
    pass


STYLES = ("course", "ascii", "latex")
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_OVERLINE = "\u0304"


def _flatten(term: Term) -> list[Term]:
    if isinstance(term, Compose):
        return _flatten(term.first) + _flatten(term.second)
    return [term]


def format_term(term: Term, style: str = "course") -> str:
    if style not in STYLES:
        raise ValueError(f"Невідомий стиль '{style}'; доступні: {', '.join(STYLES)}")
    return _fmt(term, style)


def _fmt(t: Term, s: str) -> str:
    if isinstance(t, Const):
        return {"course": f"{t.value}{_OVERLINE}", "ascii": f"const({t.value})",
                "latex": f"\\overline{{{t.value}}}"}[s]
    if isinstance(t, Deref):
        return {"course": f"{t.name}⇒", "ascii": f"{t.name}=>",
                "latex": f"{t.name}{{\\Rightarrow}}"}[s]
    if isinstance(t, Superposition):
        func = f"\\mathit{{{t.func}}}" if s == "latex" else t.func
        inner = ", ".join([func] + [_fmt(a, s) for a in t.args])
        head = {"course": "S" + str(t.arity).translate(_SUPERSCRIPT), "ascii": f"S{t.arity}",
                "latex": f"S^{{{t.arity}}}"}[s]
        return f"{head}({inner})"
    if isinstance(t, AssignFn):
        head = {"course": f"AS^{t.var}", "ascii": f"AS_{t.var}",
                "latex": f"\\mathrm{{AS}}^{{{t.var}}}"}[s]
        return f"{head}({_fmt(t.expr, s)})"
    if isinstance(t, Compose):
        sep = {"course": " · ", "ascii": " . ", "latex": " \\cdot "}[s]
        return sep.join(_fmt(part, s) for part in _flatten(t))
    if isinstance(t, IfFn):
        name = "\\mathrm{IF}" if s == "latex" else "IF"
        return f"{name}({_fmt(t.cond, s)}, {_fmt(t.then, s)}, {_fmt(t.orelse, s)})"
    if isinstance(t, WhileFn):
        name = "\\mathrm{WH}" if s == "latex" else "WH"
        return f"{name}({_fmt(t.cond, s)}, {_fmt(t.body, s)})"
    if isinstance(t, Identity):
        return "\\mathit{id}" if s == "latex" else "id"
    raise TypeError(f"Невідомий терм: {type(t).__name__}")


def term_to_dict(t: Term) -> dict[str, Any]:
    """Терм -> вкладений словник (для JSON)."""
    if isinstance(t, Const):
        return {"term": "Const", "value": t.value}
    if isinstance(t, Deref):
        return {"term": "Deref", "name": t.name}
    if isinstance(t, Superposition):
        return {"term": "Superposition", "func": t.func, "args": [term_to_dict(a) for a in t.args]}
    if isinstance(t, AssignFn):
        return {"term": "Assign", "var": t.var, "expr": term_to_dict(t.expr)}
    if isinstance(t, Compose):
        return {"term": "Compose", "first": term_to_dict(t.first), "second": term_to_dict(t.second)}
    if isinstance(t, IfFn):
        return {"term": "If", "cond": term_to_dict(t.cond), "then": term_to_dict(t.then),
                "else": term_to_dict(t.orelse)}
    if isinstance(t, WhileFn):
        return {"term": "While", "cond": term_to_dict(t.cond), "body": term_to_dict(t.body)}
    if isinstance(t, Identity):
        return {"term": "Identity"}
    raise TypeError(f"Невідомий терм: {type(t).__name__}")
