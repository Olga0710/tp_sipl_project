"""CORE-01 / CORE-02: коректні та некоректні програми, структура дерева, AST і спани."""
import pytest

from sipl import ast
from sipl.parser import parse, parse_tree
from sipl.source import SiplSyntaxError

EUCLID = "begin while ¬ M = N do if M > N then M := M - N else N := N - M end"

VALID = [
    "begin\nx := 5\nend",
    "begin\nskip\nend",
    "begin\nx := 10;\ny := 20\nend",
    "begin\nR := 1;\nwhile Y > 0 do\nbegin\nR := R * X;\nY := Y - 1\nend\nend",
    "begin\nif x = 1 then\ny := 10\nelse\ny := 20\nend",
    "begin\nbegin\na := 5\nend;\nb := a * 2\nend",
    "begin\nresult := (x + 5) * (y - 2)\nend",
    "begin\nif x > 10 then\nskip\nelse\nx := x + 1\nend",
    "begin\nif ¬(x > 5) ∨ (y = 0) then\nz := 1\nelse\nz := 0\nend",
    "begin\ni := 3;\nwhile i > 0 do\nbegin\nj := 2;\nwhile j > 0 do\nbegin\nj := j - 1\nend;\ni := i - 1\nend\nend",
    EUCLID,
    "begin if not x = 1 or y > 2 then skip else skip end",
    "begin if (x + 1) > 2 then skip else skip end",
    "begin x := -5; y := x - -3 end",
    "begin if (x > 1) ∨ (y = 2) then skip else skip end",
]

INVALID = [
    ("x := 5", "'begin'"),                                    # немає begin/end (NP1)
    ("begin\nx := 5", "'end'"),                               # немає end
    ("begin\nx 5\nend", "':='"),                              # немає :=
    ("begin\nwhile x > 0\nx := x - 1\nend", "'do'"),          # немає do
    ("begin\nif x = 5 then\nx := 1\nend", "'else'"),          # немає else
    ("begin\nx := 5 +\nend", "вираз"),                        # обірваний вираз
    ("begin\nx := (5 + 3\nend", "')'"),                       # незбалансована дужка
    ("begin\nprint x\nend", "':='"),                          # невідомий оператор
    ("begin\nwhile do\nx := 1\nend", "вираз"),                # немає умови
    ("begin\n5 := x\nend", "оператор"),                       # число зліва
    ("begin end", "оператор"),                                # порожнє тіло
    ("begin x := 1; end", "оператор"),                        # зайва ';'
    ("begin x := end end", "вираз"),                          # ключове слово як змінна
    ("begin x = 1 end", "':='"),                              # '=' замість ':='
    ("begin if x < 1 then skip else skip end", "'<'"),        # '<' не входить до SIPL
    ("begin x := 5 / 2 end", "'/'"),                          # ділення не входить до SIPL
    ("begin x := 1 end y", "зайвий"),                         # текст після end
    ("begin if x then skip else skip end", "порівняння"),     # умова без порівняння
    ("begin x := 1 y := 2 end", "'end'"),                     # пропущено ';'
    ("", "'begin'"),                                          # порожній текст
]


@pytest.mark.parametrize("src", VALID)
def test_valid_program_parses(src):
    parse(src)


@pytest.mark.parametrize("src,fragment", INVALID)
def test_invalid_program_rejected_with_message(src, fragment):
    with pytest.raises(SiplSyntaxError) as info:
        parse(src)
    assert fragment in info.value.diagnostic.message


# ---------------- дерево розбору (VIS-01) ----------------
def test_euclid_parse_tree_follows_course_bnf():
    root = parse_tree(EUCLID)
    assert (root.symbol, root.rule) == ("<програма>", "NP1")
    assert [c.symbol for c in root.children] == ["begin", "<оператор>", "end"]
    loop = root.children[1]
    assert loop.rule == "NS4"                       # while ... do ...
    assert [c.symbol for c in loop.children] == ["while", "<умова>", "do", "<оператор>"]
    neg = loop.children[1]
    assert neg.rule == "NB4"                        # ¬ <умова>
    assert neg.children[1].rule == "NB1"            # <вираз> = <вираз>
    branch = loop.children[3]
    assert branch.rule == "NS3"                     # if ... then ... else ...
    assert branch.children[1].rule == "NB2"         # <вираз> > <вираз>
    assert branch.children[3].rule == "NS1"         # M := M - N
    assert branch.children[3].children[2].rule == "NA4"


def test_variable_in_expression_goes_through_nv():
    root = parse_tree("begin x := y end")
    expr = root.children[1].children[2]
    assert (expr.symbol, expr.rule) == ("<вираз>", "NA2")
    assert (expr.children[0].symbol, expr.children[0].rule) == ("<змінна>", "NV")
    assert expr.children[0].children[0].symbol == "y"


def test_leaves_give_back_all_tokens_in_order():
    leaves = [leaf.symbol for leaf in parse_tree(EUCLID).leaves()]
    assert leaves == ["begin", "while", "¬", "M", "=", "N", "do", "if", "M", ">", "N",
                      "then", "M", ":=", "M", "-", "N", "else", "N", ":=", "N", "-", "M", "end"]


def test_every_node_span_cuts_its_own_source_text():
    src = "begin\n  x := 1;\n  y := x + 2\nend"
    root = parse_tree(src)
    assert root.span.text(src) == src
    second = root.children[1].children[2]
    assert second.span.text(src) == "y := x + 2"
    assert second.children[2].span.text(src) == "x + 2"


def test_parentheses_stay_in_parse_tree_but_not_in_ast():
    src = "begin x := (1) end"
    expr = parse_tree(src).children[1].children[2]
    assert expr.rule == "NA6"
    assert parse(src).body.value == ast.Num(1)


# ---------------- AST ----------------
def body(src):
    return parse(src).body


def test_precedence_mul_over_add():
    assert body("begin x := 1 + 2 * 3 end") == ast.Assign(
        "x", ast.BinOp("+", ast.Num(1), ast.BinOp("*", ast.Num(2), ast.Num(3))))


def test_subtraction_is_left_associative():
    assert body("begin x := 10 - 3 - 2 end").value == ast.BinOp(
        "-", ast.BinOp("-", ast.Num(10), ast.Num(3)), ast.Num(2))


def test_negative_literal_vs_binary_minus():
    assert body("begin x := y - 1 end").value == ast.BinOp("-", ast.Var("y"), ast.Num(1))
    assert body("begin x := -1 end").value == ast.Num(-1)


def test_sequence_is_right_nested():
    s = body("begin x := 1; y := 2; z := 3 end")
    assert isinstance(s, ast.Seq) and isinstance(s.second, ast.Seq)
    assert s.first == ast.Assign("x", ast.Num(1))


def test_while_body_ends_at_semicolon():
    s = body("begin while x > 0 do x := x - 1; y := 1 end")
    assert isinstance(s, ast.Seq) and isinstance(s.first, ast.While)


def test_begin_end_groups_statements():
    s = body("begin while x > 0 do begin x := x - 1; y := 1 end end")
    assert isinstance(s, ast.While)
    assert isinstance(s.body, ast.Block) and isinstance(s.body.body, ast.Seq)


def test_not_binds_tighter_than_or():
    c = body("begin if not x = 1 or y = 2 then skip else skip end").cond
    assert isinstance(c, ast.Or) and isinstance(c.left, ast.Not)


def test_condition_parentheses_vs_expression_parentheses():
    c1 = body("begin if (x > 1) or (y = 2) then skip else skip end").cond
    assert isinstance(c1, ast.Or)
    c2 = body("begin if (x + 1) > 2 then skip else skip end").cond
    assert c2 == ast.Compare(">", ast.BinOp("+", ast.Var("x"), ast.Num(1)), ast.Num(2))


def test_ast_spans_point_to_source():
    src = "begin\n  x := 1;\n  y := x + 2\nend"
    prog = parse(src)
    assert prog.span.text(src) == src
    y = prog.body.second
    assert y.span.text(src) == "y := x + 2"
    assert y.value.span.text(src) == "x + 2"
    assert (y.span.start.line, y.span.start.column) == (3, 3)


def test_negative_number_span_includes_minus():
    src = "begin x := -5 end"
    num = parse(src).body.value
    assert num.span.text(src) == "-5"


# ---------------- діагностика ----------------
def test_error_points_to_unexpected_token():
    with pytest.raises(SiplSyntaxError) as info:
        parse("begin\n  x := 5 +\nend")
    d = info.value.diagnostic
    assert (d.span.start.line, d.span.start.column) == (3, 1)
    assert "рядок 3, колонка 1" in str(info.value)


def test_error_at_end_of_input():
    with pytest.raises(SiplSyntaxError) as info:
        parse("begin x := 5")
    d = info.value.diagnostic
    assert d.span.start.column == 13
    assert "кінець програми" in d.message
