import pytest

from sipl.lexer import Lexer, TokenKind as K
from sipl.source import SiplSyntaxError


def kinds(src):
    return [t.kind for t in Lexer(src).tokenize()]


def test_empty_text_gives_only_eof():
    assert kinds("") == [K.EOF]
    assert kinds("  \n  ") == [K.EOF]


def test_assignment_tokens():
    assert kinds("X := 10") == [K.IDENT, K.ASSIGN, K.NUMBER, K.EOF]


def test_all_keywords():
    src = "begin end if then else while do skip"
    assert kinds(src) == [K.BEGIN, K.END, K.IF, K.THEN, K.ELSE, K.WHILE, K.DO, K.SKIP, K.EOF]


def test_keyword_prefix_is_still_identifier():
    toks = Lexer("whilex end1 _tmp").tokenize()
    assert [t.kind for t in toks[:3]] == [K.IDENT, K.IDENT, K.IDENT]


def test_identifiers_can_be_long_and_lowercase():
    toks = Lexer("result x_1 Y").tokenize()
    assert [t.text for t in toks[:3]] == ["result", "x_1", "Y"]


def test_operators_and_punctuation():
    assert kinds("; ( ) + - * = >") == [
        K.SEMI, K.LPAREN, K.RPAREN, K.PLUS, K.MINUS, K.STAR, K.EQ, K.GT, K.EOF]


def test_assign_is_one_token_not_colon_and_equals():
    toks = Lexer("x:=y").tokenize()
    assert [t.kind for t in toks] == [K.IDENT, K.ASSIGN, K.IDENT, K.EOF]
    assert toks[1].text == ":="


def test_logic_symbols_and_ascii_aliases():
    assert kinds("∨ or ¬ not") == [K.OR, K.OR, K.NOT, K.NOT, K.EOF]


def test_tokens_without_spaces():
    assert kinds("x:=y*2-1") == [
        K.IDENT, K.ASSIGN, K.IDENT, K.STAR, K.NUMBER, K.MINUS, K.NUMBER, K.EOF]


def test_minus_is_always_a_separate_token():
    toks = Lexer("-5").tokenize()
    assert [t.kind for t in toks] == [K.MINUS, K.NUMBER, K.EOF]


def test_token_spans_cut_exact_text():
    src = "x := 10"
    toks = Lexer(src).tokenize()
    assert [t.span.text(src) for t in toks[:3]] == ["x", ":=", "10"]


def test_tracks_lines_and_columns():
    toks = Lexer("x := 1;\n  y := 2").tokenize()
    y = toks[4]
    assert y.text == "y"
    assert (y.span.start.line, y.span.start.column) == (2, 3)


def test_eof_position_is_end_of_text():
    toks = Lexer("ab\ncd").tokenize()
    eof = toks[-1]
    assert (eof.span.start.line, eof.span.start.column) == (2, 3)


@pytest.mark.parametrize("src,line,col,fragment", [
    ("x := 1 # 2", 1, 8, "'#'"),
    ("x := 5 / 2", 1, 8, "'/'"),
    ("if x < 1", 1, 6, "'<'"),
    ("x := 1\nй := 2", 2, 1, "'й'"),
    ("x : 1", 1, 3, "':'"),
])
def test_lexical_errors_have_exact_position(src, line, col, fragment):
    with pytest.raises(SiplSyntaxError) as info:
        Lexer(src).tokenize()
    d = info.value.diagnostic
    assert (d.span.start.line, d.span.start.column) == (line, col)
    assert fragment in d.message
