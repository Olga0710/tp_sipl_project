"""Диференційне тестування: інтерпретатор і семантичний терм дають однаковий результат
на випадкових завершуваних програмах (модуль працює на класі програм, а не на прикладі)."""
import random

import pytest

from sipl.interpreter import run_source
from sipl.semantics import semantic_term
from sipl.semantics.terms import AssignFn, Compose, Const, Deref, Identity, IfFn, Superposition, WhileFn

DATA = ["a", "b", "c", "d"]
COUNTERS = ["i", "j", "k"]


class ProgramGenerator:
    def __init__(self, rng):
        self.rng = rng

    def expr(self, depth=0):
        r = self.rng.random()
        if depth >= 2 or r < 0.35:
            return str(self.rng.randint(-3, 5)) if self.rng.random() < 0.5 else self.rng.choice(DATA)
        left, right = self.expr(depth + 1), self.expr(depth + 1)
        op = self.rng.choice(["+", "-", "*"])
        text = f"{left} {op} {right}"
        return f"({text})" if self.rng.random() < 0.5 else text

    def cond(self, depth=0):
        r = self.rng.random()
        if depth < 2 and r < 0.2:
            return f"{self.rng.choice(['¬', 'not'])} ({self.cond(depth + 1)})"
        if depth < 2 and r < 0.4:
            return f"({self.cond(depth + 1)}) {self.rng.choice(['∨', 'or'])} ({self.cond(depth + 1)})"
        return f"{self.expr(1)} {self.rng.choice(['=', '>'])} {self.expr(1)}"

    def stmt(self, depth, free):
        r = self.rng.random()
        if depth >= 3 or r < 0.30:
            return f"{self.rng.choice(DATA)} := {self.expr()}"
        if r < 0.38:
            return "skip"
        if r < 0.55:
            return f"{self.stmt(depth + 1, free)}; {self.stmt(depth + 1, free)}"
        if r < 0.70:
            return f"begin {self.stmt(depth + 1, free)} end"
        if r < 0.85 or not free:
            return (f"if {self.cond()} then {self.simple(depth + 1, free)} "
                    f"else {self.simple(depth + 1, free)}")
        counter = free[0]                                   # цикл із лічильником — завершується завжди
        body = self.stmt(depth + 1, free[1:])
        return (f"begin {counter} := {self.rng.randint(0, 3)}; "
                f"while {counter} > 0 do begin {body}; {counter} := {counter} - 1 end end")

    def simple(self, depth, free):
        return f"begin {self.stmt(depth, free)} end"

    def program(self):
        return f"begin {self.stmt(0, list(COUNTERS))} end"


def apply_term(t, st):
    """Застосування терму до стану за формулами AF_* практикуму (еталон для тестів)."""
    if isinstance(t, Const):
        return t.value
    if isinstance(t, Deref):
        return st[t.name]
    if isinstance(t, Superposition):
        a = [apply_term(arg, st) for arg in t.args]
        return {"add": lambda: a[0] + a[1], "sub": lambda: a[0] - a[1], "mult": lambda: a[0] * a[1],
                "eq": lambda: a[0] == a[1], "gr": lambda: a[0] > a[1],
                "or": lambda: a[0] or a[1], "neg": lambda: not a[0]}[t.func]()
    if isinstance(t, AssignFn):
        return {**st, t.var: apply_term(t.expr, st)}
    if isinstance(t, Compose):
        return apply_term(t.second, apply_term(t.first, st))
    if isinstance(t, IfFn):
        return apply_term(t.then if apply_term(t.cond, st) else t.orelse, st)
    if isinstance(t, WhileFn):
        for _ in range(10_000):
            if not apply_term(t.cond, st):
                return st
            st = apply_term(t.body, st)
        raise AssertionError("цикл не завершився")
    if isinstance(t, Identity):
        return st
    raise AssertionError(type(t))


def programs(count=250):
    gen = ProgramGenerator(random.Random(7))
    return [gen.program() for _ in range(count)]


PROGRAMS = programs()


def test_generator_covers_all_statement_kinds():
    text = "\n".join(PROGRAMS)
    for fragment in ("while ", "if ", "skip", ":=", "begin begin", "∨", " or ", "¬", "not (", ";"):
        assert fragment in text, fragment
    assert sum("while" in p for p in PROGRAMS) > 40


@pytest.mark.parametrize("i", range(0, 250, 10))
def test_interpreter_agrees_with_semantic_term_on_random_programs(i):
    init_rng = random.Random(i)
    for src in PROGRAMS[i:i + 10]:
        init = {v: init_rng.randint(-4, 6) for v in DATA}
        expected = run_source(src, init, max_steps=200_000).state
        actual = apply_term(semantic_term(src).term, dict(init))
        assert actual == expected, src
