"""Абстрактний синтаксис SIPL: власні типізовані вузли AST.

Кожен вузол зберігає SourceSpan — фрагмент вихідного тексту. Спан не бере участі
в порівнянні (compare=False): два AST рівні, якщо рівні за структурою.
Службові символи (begin/end у виразах, ':=', ';', дужки) в AST не потрапляють.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .source import SourceSpan


def _span():
    return field(default=None, compare=False, repr=False)


class Node:
    """Базовий клас усіх вузлів AST."""
    span: Optional[SourceSpan]


# ---------- вирази ----------
class Expr(Node):
    pass


@dataclass(frozen=True)
class Num(Expr):
    value: int
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Var(Expr):
    name: str
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class BinOp(Expr):
    op: str                      # '+', '-', '*'
    left: Expr
    right: Expr
    span: Optional[SourceSpan] = _span()


# ---------- умови ----------
class Cond(Node):
    pass


@dataclass(frozen=True)
class Compare(Cond):
    op: str                      # '=', '>'
    left: Expr
    right: Expr
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Or(Cond):
    left: Cond
    right: Cond
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Not(Cond):
    operand: Cond
    span: Optional[SourceSpan] = _span()


# ---------- оператори ----------
class Stmt(Node):
    pass


@dataclass(frozen=True)
class Assign(Stmt):
    target: str
    value: Expr
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Seq(Stmt):
    first: Stmt
    second: Stmt
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class If(Stmt):
    cond: Cond
    then: Stmt
    orelse: Stmt
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class While(Stmt):
    cond: Cond
    body: Stmt
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Block(Stmt):
    body: Stmt
    span: Optional[SourceSpan] = _span()


@dataclass(frozen=True)
class Skip(Stmt):
    span: Optional[SourceSpan] = _span()


# ---------- програма ----------
@dataclass(frozen=True)
class Program(Node):
    body: Stmt
    span: Optional[SourceSpan] = _span()
