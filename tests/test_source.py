import pytest

from sipl.source import Diagnostic, Position, SiplSyntaxError, SourceSpan

SRC = "begin\n  X := 1\nend"


def make_span(start_offset, end_offset, line, col, end_line, end_col):
    return SourceSpan(
        Position(start_offset, line, col),
        Position(end_offset, end_line, end_col),
    )


def test_span_text_cuts_exact_fragment():
    span = make_span(8, 14, 2, 3, 2, 9)
    assert span.text(SRC) == "X := 1"


def test_positions_are_comparable_values():
    assert Position(0, 1, 1) == Position(0, 1, 1)
    assert Position(0, 1, 1) != Position(1, 1, 2)


def test_spans_are_immutable():
    span = make_span(0, 5, 1, 1, 1, 6)
    with pytest.raises(Exception):
        span.start = Position(1, 1, 2)


def test_diagnostic_message_has_line_and_column():
    d = Diagnostic("Очікувався оператор", make_span(8, 9, 2, 3, 2, 4))
    assert str(d) == "рядок 2, колонка 3: Очікувався оператор"


def test_syntax_error_carries_diagnostic():
    d = Diagnostic("помилка", make_span(0, 1, 1, 1, 1, 2))
    with pytest.raises(SiplSyntaxError) as info:
        raise SiplSyntaxError(d)
    assert info.value.diagnostic is d
    assert "рядок 1, колонка 1" in str(info.value)
