"""CORE-04: подієва модель та trace."""
import json

import pytest

from sipl.interpreter import SiplRuntimeError, run_source
from sipl.trace import EventKind as E


def kinds(src, init=None):
    return run_source(src, init).trace.kinds()


def test_assignment_event_sequence():
    assert kinds("begin x := 1 end") == [
        E.PROGRAM_STARTED, E.BEFORE_STATEMENT, E.VARIABLE_CHANGED, E.AFTER_STATEMENT,
        E.PROGRAM_FINISHED]


def test_if_event_sequence():
    assert kinds("begin if x = 1 then y := 5 else skip end", {"x": 1}) == [
        E.PROGRAM_STARTED,
        E.BEFORE_STATEMENT,                                   # if
        E.CONDITION_EVALUATED,
        E.BEFORE_STATEMENT, E.VARIABLE_CHANGED, E.AFTER_STATEMENT,   # y := 5
        E.AFTER_STATEMENT,                                    # if
        E.PROGRAM_FINISHED]


def test_while_checks_condition_each_iteration():
    trace = run_source("begin while x > 0 do x := x - 1 end", {"x": 2}).trace
    results = [e.data["result"] for e in trace.of(E.CONDITION_EVALUATED)]
    assert results == [True, True, False]
    assert len(trace.of(E.VARIABLE_CHANGED)) == 2
    # цикл — одне Before/After на весь оператор
    whiles = [e for e in trace.of(E.BEFORE_STATEMENT) if e.data["statement"] == "while"]
    assert len(whiles) == 1


def test_variable_changed_has_old_and_new_value():
    trace = run_source("begin x := 1; x := x + 4 end").trace
    first, second = trace.of(E.VARIABLE_CHANGED)
    assert (first.data["name"], first.data["old"], first.data["new"]) == ("x", None, 1)
    assert (second.data["old"], second.data["new"]) == (1, 5)


def test_event_spans_point_to_statement_text():
    src = "begin\n  x := 1;\n  y := x + 2\nend"
    trace = run_source(src).trace
    texts = [e.span.text(src) for e in trace.of(E.BEFORE_STATEMENT)]
    assert texts == ["x := 1", "y := x + 2"]


def test_condition_event_span_is_the_condition():
    src = "begin if x > 0 then skip else skip end"
    cond = run_source(src, {"x": 1}).trace.of(E.CONDITION_EVALUATED)[0]
    assert cond.span.text(src) == "x > 0"


def test_after_statement_state_is_a_snapshot():
    trace = run_source("begin x := 1; x := 2 end").trace
    after = trace.of(E.AFTER_STATEMENT)
    assert after[0].data["state"] == {"x": 1}
    assert after[1].data["state"] == {"x": 2}


def test_finished_event_has_final_state_and_steps():
    done = run_source("begin x := 1; y := 2 end").trace[-1]
    assert done.kind is E.PROGRAM_FINISHED
    assert done.data == {"state": {"x": 1, "y": 2}, "steps": 2}


def test_events_are_numbered_in_order():
    trace = run_source("begin x := 1 end").trace
    assert [e.index for e in trace] == list(range(len(trace)))


def test_trace_is_json_serializable_with_stable_keys():
    trace = run_source("begin x := 1 end").trace
    data = json.loads(trace.to_json())
    assert set(data[0]) == {"index", "event", "span", "data"}
    assert data[0]["event"] == "ProgramStarted"
    assert set(data[1]["span"]) == {"start", "end"}
    assert set(data[1]["span"]["start"]) == {"offset", "line", "column"}


def test_listener_receives_events_as_they_happen():
    seen = []
    result = run_source("begin x := 1 end", listener=seen.append)
    assert [e.kind for e in seen] == result.trace.kinds()


def test_failed_run_ends_with_execution_failed_event():
    with pytest.raises(SiplRuntimeError) as info:
        run_source("begin x := y end")
    last = info.value.trace[-1]
    assert last.kind is E.EXECUTION_FAILED
    assert "'y'" in last.data["message"]


def test_trace_container_api():
    trace = run_source("begin skip end").trace
    assert len(trace) == len(trace.to_list()) == 4
    assert trace[0].kind is E.PROGRAM_STARTED
