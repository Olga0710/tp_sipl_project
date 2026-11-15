
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """Позиція в тексті: зсув від початку, рядок і колонка (рядок і колонка з 1)."""
    offset: int
    line: int
    column: int


@dataclass(frozen=True)
class SourceSpan:
    """Фрагмент вихідного тексту [start, end); кінець не включається."""
    start: Position
    end: Position

    def text(self, source: str) -> str:
        """Вирізати з вихідного тексту фрагмент, який описує цей спан."""
        return source[self.start.offset:self.end.offset]


@dataclass(frozen=True)
class Diagnostic:
    """Повідомлення про помилку з точним місцем у тексті."""
    message: str
    span: SourceSpan

    def __str__(self) -> str:
        s = self.span.start
        return f"рядок {s.line}, колонка {s.column}: {self.message}"


class SiplSyntaxError(Exception):
    """Синтаксична (або лексична) помилка SIPL-програми."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic
