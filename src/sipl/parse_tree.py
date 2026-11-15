"""Конкретне дерево розбору (дерево синтаксичного виводу) SIPL.

Кожен внутрішній вузол відповідає одному правилу БНФ  (NP1, NS1..NS6,
NA1..NA6, NB1..NB5, NV, NN); листки — термінали (символи програми).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .lexer import Token
from .source import SourceSpan


@dataclass(frozen=True)
class ParseNode:
    symbol: str                      
    rule: str | None                
    children: tuple["ParseNode", ...]
    span: SourceSpan
    terminal: bool = False

    def leaves(self) -> Iterator["ParseNode"]:
        """Листки (термінали) зліва направо."""
        if self.terminal:
            yield self
        else:
            for child in self.children:
                yield from child.leaves()


def leaf(token: Token) -> ParseNode:
    return ParseNode(token.text, None, (), token.span, terminal=True)


def merged_leaf(text: str, first: Token, last: Token) -> ParseNode:
    """Один термінал із двох токенів (наприклад, від'ємне число '-5')."""
    return ParseNode(text, None, (), SourceSpan(first.span.start, last.span.end), terminal=True)


def node(symbol: str, rule: str, children: list[ParseNode]) -> ParseNode:
    span = SourceSpan(children[0].span.start, children[-1].span.end)
    return ParseNode(symbol, rule, tuple(children), span)
