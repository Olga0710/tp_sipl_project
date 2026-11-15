"""Лексер: перетворює текст SIPL-програми на послідовність токенів."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .source import Diagnostic, Position, SiplSyntaxError, SourceSpan


class TokenKind(Enum):
    NUMBER = auto()
    IDENT = auto()          # ім'я змінної
    # ключові слова
    BEGIN = auto()
    END = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    WHILE = auto()
    DO = auto()
    SKIP = auto()
    OR = auto()             # '∨' або 'or'
    NOT = auto()            # '¬' або 'not'
    # розділювачі та оператори
    ASSIGN = auto()         # :=
    SEMI = auto()           # ;
    LPAREN = auto()
    RPAREN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    EQ = auto()             # =
    GT = auto()             # >
    EOF = auto()            # кінець тексту


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    span: SourceSpan


KEYWORDS = {
    "begin": TokenKind.BEGIN,
    "end": TokenKind.END,
    "if": TokenKind.IF,
    "then": TokenKind.THEN,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "do": TokenKind.DO,
    "skip": TokenKind.SKIP,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
}

SINGLE_CHAR = {
    ";": TokenKind.SEMI,
    "(": TokenKind.LPAREN,
    ")": TokenKind.RPAREN,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "=": TokenKind.EQ,
    ">": TokenKind.GT,
    "∨": TokenKind.OR,
    "¬": TokenKind.NOT,
}


def _is_ident_start(c: str) -> bool:
    return c == "_" or (c.isascii() and c.isalpha())


def _is_ident_part(c: str) -> bool:
    return c == "_" or (c.isascii() and c.isalnum())


class Lexer:
    def __init__(self, source: str):
        self._src = source
        self._pos = 0
        self._line = 1
        self._col = 1

    # ---------- допоміжні ----------
    def _here(self) -> Position:
        return Position(self._pos, self._line, self._col)

    def _advance(self) -> None:
        if self._src[self._pos] == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        self._pos += 1

    def _more(self) -> bool:
        return self._pos < len(self._src)

    def _error(self, message: str, start: Position) -> SiplSyntaxError:
        return SiplSyntaxError(Diagnostic(message, SourceSpan(start, self._here())))

    def _make(self, kind: TokenKind, start: Position) -> Token:
        return Token(kind, self._src[start.offset:self._pos], SourceSpan(start, self._here()))

    # ---------- головний цикл ----------
    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            while self._more() and self._src[self._pos].isspace():
                self._advance()
            if not self._more():
                end = self._here()
                tokens.append(Token(TokenKind.EOF, "", SourceSpan(end, end)))
                return tokens
            tokens.append(self._next_token())

    def _next_token(self) -> Token:
        start = self._here()
        c = self._src[self._pos]

        if c.isascii() and c.isdigit():
            while self._more() and self._src[self._pos].isascii() and self._src[self._pos].isdigit():
                self._advance()
            return self._make(TokenKind.NUMBER, start)

        if _is_ident_start(c):
            while self._more() and _is_ident_part(self._src[self._pos]):
                self._advance()
            word = self._src[start.offset:self._pos]
            return self._make(KEYWORDS.get(word, TokenKind.IDENT), start)

        if c == ":":
            self._advance()
            if self._more() and self._src[self._pos] == "=":
                self._advance()
                return self._make(TokenKind.ASSIGN, start)
            raise self._error("Після ':' очікувався '=' (присвоювання записується ':=')", start)

        if c in SINGLE_CHAR:
            self._advance()
            return self._make(SINGLE_CHAR[c], start)

        self._advance()
        raise self._error(f"Недопустимий символ '{c}'", start)
