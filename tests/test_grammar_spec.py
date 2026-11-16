"""CORE-01: граматика grammar/sipl.ebnf — машинозчитувана специфікація.

Тест читає сам файл EBNF, генерує з нього речення мови й перевіряє, що парсер їх приймає
(повнота парсера щодо специфікації), а також що жоден власний префікс програми не приймається.
"""
import random
import re
from pathlib import Path

import pytest

from sipl.lexer import KEYWORDS
from sipl.parser import parse, parse_tree
from sipl.source import SiplSyntaxError

ROOT = Path(__file__).resolve().parent.parent
LEXICAL = {"ident", "number", "letter", "digit"}


# ---------------------------------------------------------------- читач EBNF
def tokenize(text):
    text = re.sub(r"\(\*.*?\*\)", " ", text, flags=re.S)          # коментарі
    return re.findall(r'"[^"]*"|[A-Za-z_][A-Za-z0-9_]*|[=,|{}\[\]();]', text)


def read_ebnf(path):
    toks = tokenize(path.read_text(encoding="utf-8"))
    pos = 0

    def peek():
        return toks[pos] if pos < len(toks) else None

    def take(expected=None):
        nonlocal pos
        tok = toks[pos]
        assert expected is None or tok == expected, f"очікувалось {expected!r}, знайдено {tok!r}"
        pos += 1
        return tok

    def alt():
        options = [seq()]
        while peek() == "|":
            take("|")
            options.append(seq())
        return options[0] if len(options) == 1 else ("alt", options)

    def seq():
        items = [term()]
        while peek() == ",":
            take(",")
            items.append(term())
        return items[0] if len(items) == 1 else ("seq", items)

    def term():
        tok = peek()
        if tok.startswith('"'):
            take()
            return ("lit", tok[1:-1])
        if tok == "{":
            take("{")
            inner = alt()
            take("}")
            return ("rep", inner)
        if tok == "[":
            take("[")
            inner = alt()
            take("]")
            return ("opt", inner)
        if tok == "(":
            take("(")
            inner = alt()
            take(")")
            return inner
        take()
        return ("name", tok)

    rules = {}
    while pos < len(toks):
        name = take()
        take("=")
        rules[name] = alt()
        take(";")
    return rules


RULES = read_ebnf(ROOT / "grammar" / "sipl.ebnf")


def names_in(expr):
    kind = expr[0]
    if kind == "name":
        yield expr[1]
    elif kind in ("seq", "alt"):
        for e in expr[1]:
            yield from names_in(e)
    elif kind in ("rep", "opt"):
        yield from names_in(expr[1])


# ---------------------------------------------------------------- генератор речень
class Generator:
    def __init__(self, rules, rng, max_depth=7):
        self.rules, self.rng, self.max_depth = rules, rng, max_depth
        self.min_depth = {n: float("inf") for n in rules}
        changed = True
        while changed:                                           # мінімальна глибина виведення кожного правила
            changed = False
            for n, e in rules.items():
                d = 1 + self._min(e)
                if d < self.min_depth[n]:
                    self.min_depth[n], changed = d, True

    def _min(self, e):
        kind = e[0]
        if kind == "lit":
            return 0
        if kind == "name":
            return self.min_depth[e[1]]
        if kind == "seq":
            return max(self._min(x) for x in e[1])
        if kind == "alt":
            return min(self._min(x) for x in e[1])
        return 0                                                  # rep / opt можуть бути порожніми

    def gen(self, e, depth):
        kind = e[0]
        if kind == "lit":
            return [e[1]]
        if kind == "name":
            name = e[1]
            if name in LEXICAL:
                while True:
                    word = "".join(self.gen(self.rules[name], depth + 1))
                    if name != "ident" or word not in KEYWORDS:
                        return [word]
            return self.gen(self.rules[name], depth + 1)
        if kind == "seq":
            return [t for x in e[1] for t in self.gen(x, depth)]
        if kind == "alt":
            options = e[1]
            if depth > self.max_depth:
                best = min(self._min(x) for x in options)
                options = [x for x in options if self._min(x) == best]
            return self.gen(self.rng.choice(options), depth)
        if kind == "opt":
            return self.gen(e[1], depth) if depth <= self.max_depth and self.rng.random() < 0.5 else []
        if kind == "rep":
            n = 0 if depth > self.max_depth else self.rng.choice([0, 0, 1, 2])
            return [t for _ in range(n) for t in self.gen(e[1], depth)]
        raise AssertionError(kind)

    def sentence(self):
        return self.gen(("name", "program"), 0)


def sentences(count, seed=2026):
    rng = random.Random(seed)
    gen = Generator(RULES, rng)
    return [gen.sentence() for _ in range(count)]


# ---------------------------------------------------------------- самоузгодженість специфікації
def test_ebnf_defines_the_course_rules():
    for name in ("program", "statement", "simple", "assign", "if", "while", "block", "skip",
                 "expr", "term", "factor", "cond", "not_cond", "cond_atom", "variable", "number"):
        assert name in RULES


def test_every_referenced_rule_is_defined():
    for name, expr in RULES.items():
        for ref in names_in(expr):
            assert ref in RULES, f"правило '{name}' посилається на невизначене '{ref}'"


def test_every_rule_is_reachable_from_program():
    seen, todo = set(), ["program"]
    while todo:
        name = todo.pop()
        if name not in seen:
            seen.add(name)
            todo.extend(names_in(RULES[name]))
    assert set(RULES) - seen == {"keyword"}              # keyword лише описує виняток для ident


def test_keyword_rule_matches_the_lexer():
    words = {e[1] for e in RULES["keyword"][1]}
    assert words == set(KEYWORDS)


# ---------------------------------------------------------------- парсер проти специфікації
SAMPLES = sentences(300)


def test_generator_produces_varied_sentences():
    assert len({" ".join(s) for s in SAMPLES}) > 200
    assert max(len(s) for s in SAMPLES) > 40
    assert all(s[0] == "begin" and s[-1] == "end" for s in SAMPLES)


@pytest.mark.parametrize("i", range(0, 300, 6))
def test_parser_accepts_sentences_generated_from_the_ebnf(i):
    for tokens in SAMPLES[i:i + 6]:
        parse(" ".join(tokens))


def test_parse_tree_leaves_reproduce_the_generated_sentence():
    for tokens in SAMPLES[:150]:
        leaves = [leaf.symbol for leaf in parse_tree(" ".join(tokens)).leaves()]
        assert leaves == tokens


def test_generated_sentences_exercise_every_course_rule():
    used = set()

    def collect(node):
        if node.rule:
            used.add(node.rule)
        for child in node.children:
            collect(child)

    for tokens in SAMPLES:
        collect(parse_tree(" ".join(tokens)))
    expected = {"NP1", "NV", "NN"} | {f"NS{i}" for i in range(1, 7)} | {f"NA{i}" for i in range(1, 7)} \
        | {f"NB{i}" for i in range(1, 6)}
    assert expected <= used


def test_every_proper_prefix_of_a_valid_program_is_rejected():
    for tokens in SAMPLES[:60]:
        for cut in range(len(tokens)):
            with pytest.raises(SiplSyntaxError):
                parse(" ".join(tokens[:cut]))


def test_extra_token_after_a_valid_program_is_rejected():
    for tokens in SAMPLES[:40]:
        with pytest.raises(SiplSyntaxError):
            parse(" ".join(tokens) + " x")


def test_leaf_numbering_works_for_every_generated_program():
    """Нумерація листків не прив'язана до прикладу: перевіряємо на 150 згенерованих програмах."""
    import json
    import xml.etree.ElementTree as ET

    from sipl.visualization import ParseTreeView

    for tokens in SAMPLES[:150]:
        view = ParseTreeView(" ".join(tokens))
        expected = " ".join(f"{i} {t}" for i, t in enumerate(tokens, start=1))
        assert view.leaf_sequence() == expected
        assert view.to_text(leaves=True).rstrip().endswith(expected)

        orders = []

        def collect(d):
            if d["terminal"]:
                orders.append((d["order"], d["symbol"]))
            else:
                for child in d["children"]:
                    collect(child)

        collect(json.loads(view.to_json()))
        assert orders == list(enumerate(tokens, start=1))

        svg = ET.fromstring(view.to_svg())
        nums = [t.text for t in svg.iter("{http://www.w3.org/2000/svg}text") if t.get("class") == "order"]
        assert nums == [str(i) for i in range(1, len(tokens) + 1)]
