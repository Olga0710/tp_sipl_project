import json

from sipl import ast
from sipl.ast_format import ast_to_dict, ast_to_text, input_variables, variables
from sipl.parser import parse


def test_ast_to_dict_shape_and_json_serializable():
    d = ast_to_dict(parse("begin x := 1 + y end"))
    assert d["node"] == "Program"
    assign = d["body"]
    assert (assign["node"], assign["target"]) == ("Assign", "x")
    assert assign["value"]["node"] == "BinOp" and assign["value"]["op"] == "+"
    assert assign["value"]["left"] == {"node": "Num", "value": 1, "span": assign["value"]["left"]["span"]}
    json.dumps(d)


def test_ast_to_dict_has_spans_unless_disabled():
    prog = parse("begin x := 1 end")
    assert set(ast_to_dict(prog)["span"]) == {"start", "end"}
    assert "span" not in ast_to_dict(prog, spans=False)["body"]


def test_ast_to_dict_of_hand_built_node_without_span():
    assert ast_to_dict(ast.Num(5)) == {"node": "Num", "value": 5}


def test_ast_to_text_shows_structure_and_positions():
    text = ast_to_text(parse("begin\n  while x > 0 do x := x - 1\nend"))
    lines = text.splitlines()
    assert lines[0].startswith("Program")
    assert any("While" in line for line in lines)
    assert any("cond: Compare >" in line for line in lines)
    assert any("Assign x :=" in line for line in lines)
    assert any("Num 0" in line for line in lines)
    assert any("2:3" in line for line in lines)


def test_variables_read_and_assigned():
    prog = parse("begin x := y + 1; if x > z then skip else w := 2 end")
    read, assigned = variables(prog)
    assert read == {"x", "y", "z"} and assigned == {"x", "w"}


def test_input_variables_are_those_read_before_assigned():
    assert input_variables(parse("begin x := y + 1; z := x end")) == ["y"]
    assert input_variables(parse(
        "begin while ¬ M = N do if M > N then M := M - N else N := N - M end")) == ["M", "N"]
    assert input_variables(parse("begin x := 1 end")) == []


def test_variable_assigned_and_read_in_same_statement_is_input():
    assert input_variables(parse("begin x := x + 1 end")) == ["x"]


def test_power_example_needs_x_and_y():
    assert input_variables(parse(
        "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end")) == ["X", "Y"]


def test_after_if_only_variables_set_in_both_branches_are_defined():
    both = "begin if a = 1 then y := 1 else y := 2; z := y end"
    one = "begin if a = 1 then y := 1 else skip; z := y end"
    assert input_variables(parse(both)) == ["a"]
    assert input_variables(parse(one)) == ["a", "y"]


def test_assignment_inside_loop_is_not_guaranteed_after_it():
    assert input_variables(parse("begin while x > 0 do y := 1; z := y end")) == ["x", "y"]
