"""CORE-03: виконання програм SIPL."""
import pytest

from sipl import ast
from sipl.interpreter import (
    Interpreter, SiplRuntimeError, StepLimitExceeded, run, run_source,
)
from sipl.parser import parse


def state_of(src, init=None, **kw):
    return run_source(src, init, **kw).state


# ---------- вирази та оператори ----------
def test_assignment_and_precedence():
    assert state_of("begin x := 1 + 2 * 3 end") == {"x": 7}


def test_subtraction_is_left_associative():
    assert state_of("begin x := 10 - 3 - 2 end") == {"x": 5}


def test_negative_numbers():
    assert state_of("begin x := -5; y := x - -3 end") == {"x": -5, "y": -2}


def test_skip_leaves_state_unchanged():
    assert state_of("begin skip end", {"a": 1}) == {"a": 1}


def test_sequence_runs_left_to_right():
    assert state_of("begin x := 1; x := x + 1; x := x * 10 end") == {"x": 20}


def test_block_groups_statements():
    assert state_of("begin begin a := 5 end; b := a * 2 end") == {"a": 5, "b": 10}


@pytest.mark.parametrize("x,expected", [(1, 10), (2, 20)])
def test_if_else_branches(x, expected):
    src = "begin if x = 1 then y := 10 else y := 20 end"
    assert state_of(src, {"x": x}) == {"x": x, "y": expected}


def test_while_computes_power():
    src = """begin
      R := 1;
      while Y > 0 do
      begin R := R * X; Y := Y - 1 end
    end"""
    assert state_of(src, {"X": 2, "Y": 10}) == {"X": 2, "Y": 0, "R": 1024}


def test_while_with_false_condition_never_runs_body():
    assert state_of("begin while x > 0 do x := x - 1 end", {"x": 0}) == {"x": 0}


EUCLID = "begin while ¬ M = N do if M > N then M := M - N else N := N - M end"


@pytest.mark.parametrize("m,n,g", [(12, 18, 6), (7, 5, 1), (9, 9, 9), (100, 75, 25)])
def test_euclid_gcd(m, n, g):
    assert state_of(EUCLID, {"M": m, "N": n}) == {"M": g, "N": g}


def test_nested_loops():
    src = """begin
      i := 3;
      while i > 0 do
      begin
        j := 2;
        while j > 0 do begin j := j - 1 end;
        i := i - 1
      end
    end"""
    assert state_of(src) == {"i": 0, "j": 0}


@pytest.mark.parametrize("x,y,expected", [(3, 1, 1), (9, 1, 0), (9, 0, 1)])
def test_logic_not_and_or(x, y, expected):
    src = "begin if ¬ x > 5 ∨ y = 0 then z := 1 else z := 0 end"
    assert state_of(src, {"x": x, "y": y})["z"] == expected


def test_ascii_logic_keywords_behave_like_symbols():
    src = "begin if not x > 5 or y = 0 then z := 1 else z := 0 end"
    assert state_of(src, {"x": 9, "y": 0})["z"] == 1


def test_initial_state_is_not_mutated():
    init = {"x": 1}
    state_of("begin x := 2 end", init)
    assert init == {"x": 1}


def test_run_accepts_ast_directly():
    assert run(parse("begin x := 4 end")).state == {"x": 4}


# ---------- кроки ----------
def test_steps_count_elementary_statements():
    assert run_source("begin x := 1; y := 2 end").steps == 2


def test_steps_count_condition_checks():
    # x := 3 (1) + 4 перевірки умови + 3 присвоювання в тілі
    assert run_source("begin x := 3; while x > 0 do x := x - 1 end").steps == 8


# ---------- помилки виконання ----------
def test_uninitialized_variable_error_has_position():
    with pytest.raises(SiplRuntimeError) as info:
        run_source("begin\n x := y + 1\nend")
    d = info.value.diagnostic
    assert (d.span.start.line, d.span.start.column) == (2, 7)
    assert "'y'" in d.message


def test_infinite_loop_is_stopped_by_step_limit():
    with pytest.raises(StepLimitExceeded) as info:
        run_source("begin while 1 = 1 do skip end", max_steps=50)
    assert isinstance(info.value, SiplRuntimeError)
    assert "50" in info.value.diagnostic.message


def test_error_keeps_state_and_trace():
    with pytest.raises(SiplRuntimeError) as info:
        run_source("begin x := 1; y := z end")
    assert info.value.state == {"x": 1}
    assert info.value.trace is not None
    assert info.value.trace[-1].kind.value == "ExecutionFailed"


def test_or_needs_both_operands_defined():
    with pytest.raises(SiplRuntimeError):
        run_source("begin if x = 1 or y = 1 then skip else skip end", {"x": 1})


def test_hand_built_ast_without_spans_still_reports_error():
    prog = ast.Program(ast.Assign("x", ast.Var("y")))
    with pytest.raises(SiplRuntimeError) as info:
        run(prog)
    assert info.value.diagnostic.span.start.line == 1


def test_unknown_node_is_rejected():
    class Weird(ast.Stmt):
        span = None
    with pytest.raises(TypeError):
        Interpreter().run(ast.Program(Weird()))


def test_interpreter_object_can_be_reused():
    interp = Interpreter()
    assert interp.run(parse("begin x := 1 end")).state == {"x": 1}
    assert interp.run(parse("begin y := 2 end")).state == {"y": 2}
