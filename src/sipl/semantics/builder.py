"""Побудова семантичного терму SIPL-програми за правилами"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .. import ast
from ..parser import parse
from .terms import (
    AssignFn, Compose, Const, Deref, Identity, IfFn, Superposition, Term, WhileFn,
)

_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_BAR = "\u0304"

_ARITH_RULES = {"+": ("NS_A_Add", "add"), "-": ("NS_A_Sub", "sub"), "*": ("NS_A_Mult", "mult")}
_COMPARE_RULES = {"=": ("NS_B_eq", "eq"), ">": ("NS_B_gr", "gr")}


@dataclass(frozen=True)
class RuleStep:
    index: int
    rule: str          # NS_Prog, NS_Stm_As, ...
    lhs: str           # sem_S(x := 1)
    rhs: str           # AS^x(sem_A(1))

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "rule": self.rule, "lhs": self.lhs, "rhs": self.rhs}


@dataclass(frozen=True)
class Construction:
    term: Term
    steps: tuple[RuleStep, ...]


def build_term(program: ast.Program, source: Optional[str] = None) -> Construction:
    """sem_P(програма). Якщо задано source, у кроках показуються фрагменти вихідного тексту."""
    builder = _Builder(source)
    term = builder.prog(program)
    return Construction(term, tuple(builder.steps))


def semantic_term(source: str) -> Construction:
    """Розібрати текст програми й побудувати її семантичний терм."""
    return build_term(parse(source), source)


class _Builder:
    def __init__(self, source: Optional[str]):
        self.source = source
        self.steps: list[RuleStep] = []

    # ---------- допоміжні ----------
    def _frag(self, node: ast.Node) -> str:
        if self.source is not None and node.span is not None:
            return " ".join(node.span.text(self.source).split())
        return type(node).__name__

    def _emit(self, rule: str, lhs: str, rhs: str) -> None:
        self.steps.append(RuleStep(len(self.steps) + 1, rule, lhs, rhs))

    # ---------- sem_P ----------
    def prog(self, node: ast.Program) -> Term:
        self._emit("NS_Prog", f"sem_P({self._frag(node)})", f"sem_S({self._frag(node.body)})")
        return self.stm(node.body)

    # ---------- sem_S ----------
    def stm(self, node: ast.Stmt) -> Term:
        f = self._frag
        if isinstance(node, ast.Assign):
            self._emit("NS_Stm_As", f"sem_S({f(node)})", f"AS^{node.target}(sem_A({f(node.value)}))")
            return AssignFn(node.target, self.aexp(node.value))
        if isinstance(node, ast.Seq):
            self._emit("NS_Stm_Seq", f"sem_S({f(node)})",
                       f"sem_S({f(node.first)}) · sem_S({f(node.second)})")
            first = self.stm(node.first)
            return Compose(first, self.stm(node.second))
        if isinstance(node, ast.If):
            self._emit("NS_Stm_If", f"sem_S({f(node)})",
                       f"IF(sem_B({f(node.cond)}), sem_S({f(node.then)}), sem_S({f(node.orelse)}))")
            cond = self.bexp(node.cond)
            then = self.stm(node.then)
            return IfFn(cond, then, self.stm(node.orelse))
        if isinstance(node, ast.While):
            self._emit("NS_Stm_Wh", f"sem_S({f(node)})",
                       f"WH(sem_B({f(node.cond)}), sem_S({f(node.body)}))")
            cond = self.bexp(node.cond)
            return WhileFn(cond, self.stm(node.body))
        if isinstance(node, ast.Block):
            self._emit("NS_Stm_BE", f"sem_S({f(node)})", f"sem_S({f(node.body)})")
            return self.stm(node.body)
        if isinstance(node, ast.Skip):
            self._emit("NS_Stm_skip", "sem_S(skip)", "id")
            return Identity()
        raise TypeError(f"Невідомий вузол оператора: {type(node).__name__}")

    # ---------- sem_A ----------
    def aexp(self, node: ast.Expr) -> Term:
        f = self._frag
        if isinstance(node, ast.Num):
            self._emit("NS_A_Num", f"sem_A({f(node)})", f"{node.value}{_BAR}")
            return Const(node.value)
        if isinstance(node, ast.Var):
            self._emit("NS_A_Var", f"sem_A({node.name})", f"{node.name}⇒")
            return Deref(node.name)
        if isinstance(node, ast.BinOp):
            rule, func = _ARITH_RULES[node.op]
            self._emit(rule, f"sem_A({f(node)})",
                       f"S²({func}, sem_A({f(node.left)}), sem_A({f(node.right)}))")
            left = self.aexp(node.left)
            return Superposition(func, (left, self.aexp(node.right)))
        raise TypeError(f"Невідомий вузол виразу: {type(node).__name__}")

    # ---------- sem_B ----------
    def bexp(self, node: ast.Cond) -> Term:
        f = self._frag
        if isinstance(node, ast.Compare):
            rule, func = _COMPARE_RULES[node.op]
            self._emit(rule, f"sem_B({f(node)})",
                       f"S²({func}, sem_A({f(node.left)}), sem_A({f(node.right)}))")
            left = self.aexp(node.left)
            return Superposition(func, (left, self.aexp(node.right)))
        if isinstance(node, ast.Or):
            self._emit("NS_B_or", f"sem_B({f(node)})",
                       f"S²(or, sem_B({f(node.left)}), sem_B({f(node.right)}))")
            left = self.bexp(node.left)
            return Superposition("or", (left, self.bexp(node.right)))
        if isinstance(node, ast.Not):
            self._emit("NS_B_neg", f"sem_B({f(node)})", f"S¹(neg, sem_B({f(node.operand)}))")
            return Superposition("neg", (self.bexp(node.operand),))
        raise TypeError(f"Невідомий вузол умови: {type(node).__name__}")
