"""SEM-01: семантичні терми. Golden-тести за практикумом (ПР 2) + звірка з інтерпретатором."""
import contextlib
import io
import json

import pytest

from sipl import ast
from sipl.cli import main
from sipl.interpreter import run_source
from sipl.parser import parse
from sipl.semantics import STYLES, build_term, format_term, semantic_term, term_to_dict
from sipl.semantics.terms import (
    AssignFn, Compose, Const, Deref, Identity, IfFn, Superposition, WhileFn,
)

BAR = "\u0304"

# Програма x^y (ПР 1-2, с. 9-16)
POWER = """begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end"""
EUCLID = "begin while ¬ M = N do if M > N then M := M - N else N := N - M end"


def term(src, style="course"):
    return format_term(semantic_term(src).term, style)


# 
def test_power_term_matches_the_textbook():
    expected = (f"AS^R(1{BAR}) · WH(S²(gr, Y⇒, 0{BAR}), "
                f"AS^R(S²(mult, R⇒, X⇒)) · AS^Y(S²(sub, Y⇒, 1{BAR})))")
    assert term(POWER) == expected


def test_power_term_in_ascii_and_latex():
    assert term(POWER, "ascii") == (
        "AS_R(const(1)) . WH(S2(gr, Y=>, const(0)), AS_R(S2(mult, R=>, X=>)) . AS_Y(S2(sub, Y=>, const(1))))")
    latex = term(POWER, "latex")
    assert latex.startswith("\\mathrm{AS}^{R}(\\overline{1}) \\cdot \\mathrm{WH}(S^{2}(\\mathit{gr}, Y{\\Rightarrow}")
    assert latex.count("\\cdot") == 2


def test_power_derivation_follows_the_textbook_order():
    steps = semantic_term(POWER).steps
    assert [s.rule for s in steps] == [
        "NS_Prog", "NS_Stm_Seq", "NS_Stm_As", "NS_A_Num",            # R := 1
        "NS_Stm_Wh", "NS_B_gr", "NS_A_Var", "NS_A_Num",              # while Y > 0
        "NS_Stm_BE", "NS_Stm_Seq",                                   # begin ... end; послідовність
        "NS_Stm_As", "NS_A_Mult", "NS_A_Var", "NS_A_Var",            # R := R * X
        "NS_Stm_As", "NS_A_Sub", "NS_A_Var", "NS_A_Num"]             # Y := Y - 1


def test_derivation_steps_show_source_fragments():
    steps = semantic_term(POWER).steps
    assert steps[0].lhs == "sem_P(begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end)"
    assert steps[0].rhs == "sem_S(R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end)"
    assert (steps[2].lhs, steps[2].rhs) == ("sem_S(R := 1)", "AS^R(sem_A(1))")
    assert (steps[3].lhs, steps[3].rhs) == ("sem_A(1)", f"1{BAR}")
    assert (steps[5].lhs, steps[5].rhs) == ("sem_B(Y > 0)", "S²(gr, sem_A(Y), sem_A(0))")
    assert [s.index for s in steps] == list(range(1, len(steps) + 1))


def test_euclid_golden_term():
    assert term(EUCLID) == (
        "WH(S¹(neg, S²(eq, M⇒, N⇒)), IF(S²(gr, M⇒, N⇒), "
        "AS^M(S²(sub, M⇒, N⇒)), AS^N(S²(sub, N⇒, M⇒))))")


# ---------------- по одному правилу ----------------
@pytest.mark.parametrize("body,expected", [
    ("skip", "id"),                                                         # NS_Stm_skip
    ("x := 5", f"AS^x(5{BAR})"),                                            # NS_Stm_As + NS_A_Num
    ("x := y", "AS^x(y⇒)"),                                                 # NS_A_Var
    ("x := y + 1", f"AS^x(S²(add, y⇒, 1{BAR}))"),                           # NS_A_Add
    ("x := y - 1", f"AS^x(S²(sub, y⇒, 1{BAR}))"),                           # NS_A_Sub
    ("x := y * 2", f"AS^x(S²(mult, y⇒, 2{BAR}))"),                          # NS_A_Mult
    ("x := 1 + 2 * 3", f"AS^x(S²(add, 1{BAR}, S²(mult, 2{BAR}, 3{BAR})))"),  # пріоритет
    ("x := 10 - 3 - 2", f"AS^x(S²(sub, S²(sub, 10{BAR}, 3{BAR}), 2{BAR}))"),  # лівоасоціативність
    ("x := (y)", "AS^x(y⇒)"),                                               # NS_A_Par
    ("x := ((1 + 2)) * 3", f"AS^x(S²(mult, S²(add, 1{BAR}, 2{BAR}), 3{BAR}))"),
    ("x := -5", f"AS^x(-5{BAR})"),                                          # від'ємна константа
    ("x := 1; y := 2; z := 3", f"AS^x(1{BAR}) · AS^y(2{BAR}) · AS^z(3{BAR})"),   # NS_Stm_Seq
    ("begin x := 1 end; y := 2", f"AS^x(1{BAR}) · AS^y(2{BAR})"),           # NS_Stm_BE
    ("if x > 0 then y := 1 else skip", f"IF(S²(gr, x⇒, 0{BAR}), AS^y(1{BAR}), id)"),   # NS_Stm_If
    ("while x > 0 do x := x - 1", f"WH(S²(gr, x⇒, 0{BAR}), AS^x(S²(sub, x⇒, 1{BAR})))"),  # NS_Stm_Wh
    ("if x = 1 then skip else skip", f"IF(S²(eq, x⇒, 1{BAR}), id, id)"),    # NS_B_eq
    ("if ¬ x = 1 then skip else skip", f"IF(S¹(neg, S²(eq, x⇒, 1{BAR})), id, id)"),   # NS_B_neg
    ("if x = 1 ∨ y = 2 then skip else skip",
     f"IF(S²(or, S²(eq, x⇒, 1{BAR}), S²(eq, y⇒, 2{BAR})), id, id)"),        # NS_B_or
    ("if ¬ (x > 5) ∨ y = 0 then skip else skip",
     f"IF(S²(or, S¹(neg, S²(gr, x⇒, 5{BAR})), S²(eq, y⇒, 0{BAR})), id, id)"),   # NS_B_Par + пріоритет ¬
    ("if (x = 1) then skip else skip", f"IF(S²(eq, x⇒, 1{BAR}), id, id)"),
])
def test_single_rule_terms(body, expected):
    assert term(f"begin {body} end") == expected


def test_sequence_term_is_right_nested_but_printed_flat():
    t = semantic_term("begin a := 1; b := 2; c := 3 end").term
    assert isinstance(t, Compose) and isinstance(t.second, Compose)


def test_term_structure_types():
    t = semantic_term(POWER).term
    assert isinstance(t, Compose) and isinstance(t.first, AssignFn)
    loop = t.second
    assert isinstance(loop, WhileFn) and isinstance(loop.cond, Superposition)
    assert loop.cond == Superposition("gr", (Deref("Y"), Const(0)))
    assert isinstance(semantic_term("begin skip end").term, Identity)
    assert isinstance(semantic_term("begin if x = 1 then skip else skip end").term, IfFn)


def test_terms_are_comparable_by_value():
    assert semantic_term("begin x := 1 end").term == semantic_term("begin   x := 1   end").term
    assert semantic_term("begin x := 1 end").term != semantic_term("begin x := 2 end").term


def test_every_ast_node_gives_exactly_one_rule_step():
    steps = semantic_term(POWER).steps
    nodes = []

    def count(n):
        nodes.append(n)
        for v in vars(n).values():
            if isinstance(v, ast.Node):
                count(v)

    count(parse(POWER))
    assert len(steps) == len(nodes)              # Program -> NS_Prog, кожен вузол AST -> одне правило


def test_build_term_without_source_still_works():
    result = build_term(parse("begin x := 1 end"))
    assert format_term(result.term) == f"AS^x(1{BAR})"
    assert result.steps[0].rule == "NS_Prog"


def test_unknown_style_is_rejected():
    with pytest.raises(ValueError):
        format_term(semantic_term("begin skip end").term, "xml")


def test_styles_constant():
    assert STYLES == ("course", "ascii", "latex")


def test_term_to_dict_is_json_serializable():
    d = term_to_dict(semantic_term(POWER).term)
    json.dumps(d)
    assert d["term"] == "Compose"
    assert d["second"]["term"] == "While"
    assert d["second"]["cond"] == {"term": "Superposition", "func": "gr",
                                   "args": [{"term": "Deref", "name": "Y"}, {"term": "Const", "value": 0}]}


# ---------------- звірка семантики терму з інтерпретатором ----------------
def apply_term(t, st):
    """Застосування терму до стану за формулами AF_* практикуму (еталон для тестів)."""
    if isinstance(t, Const):
        return t.value
    if isinstance(t, Deref):
        return st[t.name]                                                       # AF_DNM
    if isinstance(t, Superposition):
        a = [apply_term(arg, st) for arg in t.args]                            # AF_S
        return {"add": lambda: a[0] + a[1], "sub": lambda: a[0] - a[1], "mult": lambda: a[0] * a[1],
                "eq": lambda: a[0] == a[1], "gr": lambda: a[0] > a[1],
                "or": lambda: a[0] or a[1], "neg": lambda: not a[0]}[t.func]()
    if isinstance(t, AssignFn):
        return {**st, t.var: apply_term(t.expr, st)}                           # AF_AS
    if isinstance(t, Compose):
        return apply_term(t.second, apply_term(t.first, st))                   # AF_SEQ
    if isinstance(t, IfFn):
        return apply_term(t.then if apply_term(t.cond, st) else t.orelse, st)  # AF_IF
    if isinstance(t, WhileFn):                                                 # AF_WH
        for _ in range(10_000):
            if not apply_term(t.cond, st):
                return st
            st = apply_term(t.body, st)
        raise AssertionError("цикл не завершився")
    if isinstance(t, Identity):
        return st                                                              # AF_ID
    raise AssertionError(type(t))


def test_textbook_test_run_power_x5_y2_gives_r25():
    st = apply_term(semantic_term(POWER).term, {"X": 5, "Y": 2})
    assert st == {"X": 5, "Y": 0, "R": 25}


@pytest.mark.parametrize("src,init", [
    (POWER, {"X": 2, "Y": 10}),
    (POWER, {"X": 3, "Y": 0}),
    (EUCLID, {"M": 12, "N": 18}),
    (EUCLID, {"M": 100, "N": 75}),
    ("begin if x > 5 then y := 1 else y := 2 end", {"x": 9}),
    ("begin if x > 5 then y := 1 else y := 2 end", {"x": 1}),
    ("begin if ¬ x > 5 ∨ y = 0 then z := 1 else z := 0 end", {"x": 9, "y": 0}),
    ("begin if ¬ x > 5 ∨ y = 0 then z := 1 else z := 0 end", {"x": 9, "y": 3}),
    ("begin i := 3; while i > 0 do begin j := 2; while j > 0 do j := j - 1; i := i - 1 end end", {}),
    ("begin x := -5; y := x * x - 3; skip end", {}),
    ("begin begin a := 1 end; b := a + (a + 1) * 2 end", {}),
])
def test_term_semantics_agrees_with_the_interpreter(src, init):
    assert apply_term(semantic_term(src).term, dict(init)) == run_source(src, init).state


# ---------------- CLI: sipl sem ----------------
def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp_path, text):
    path = tmp_path / "p.sipl"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_cli_sem_prints_term(tmp_path):
    code, out, _ = cli("sem", write(tmp_path, POWER))
    assert code == 0 and out.strip() == term(POWER)


def test_cli_sem_styles(tmp_path):
    path = write(tmp_path, "begin x := 1 end")
    assert cli("sem", path, "--style", "ascii")[1].strip() == "AS_x(const(1))"
    assert cli("sem", path, "--style", "latex")[1].strip() == "\\mathrm{AS}^{x}(\\overline{1})"
    assert cli("sem", path, "--style", "xml")[0] == 3


def test_cli_sem_steps(tmp_path):
    code, out, _ = cli("sem", write(tmp_path, POWER), "--steps")
    assert code == 0
    assert "[NS_Prog]" in out and "[NS_Stm_Wh]" in out and "[NS_A_Mult]" in out
    assert out.count("\n") > 18


def test_cli_sem_json(tmp_path):
    code, out, _ = cli("sem", write(tmp_path, POWER), "--json", "--steps")
    data = json.loads(out)
    assert code == 0 and data["command"] == "sem" and data["ok"] is True and data["schema"] == 1
    assert data["text"] == term(POWER) and data["style"] == "course"
    assert data["term"]["term"] == "Compose"
    assert data["steps"][0] == {"index": 1, "rule": "NS_Prog", "lhs": data["steps"][0]["lhs"],
                                "rhs": data["steps"][0]["rhs"]}


def test_cli_sem_json_without_steps_has_no_steps_key(tmp_path):
    data = json.loads(cli("sem", write(tmp_path, POWER), "--json")[1])
    assert "steps" not in data


def test_cli_sem_syntax_error_exit_1(tmp_path):
    assert cli("sem", write(tmp_path, "begin x := end"))[0] == 1
