"""Подієва модель виконання: події та trace (CORE-04)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterator, Optional

from .source import SourceSpan


class EventKind(str, Enum):
    PROGRAM_STARTED = "ProgramStarted"
    BEFORE_STATEMENT = "BeforeStatement"
    CONDITION_EVALUATED = "ConditionEvaluated"
    VARIABLE_CHANGED = "VariableChanged"
    AFTER_STATEMENT = "AfterStatement"
    PROGRAM_FINISHED = "ProgramFinished"
    EXECUTION_FAILED = "ExecutionFailed"


@dataclass(frozen=True)
class Event:
    index: int                       # порядковий номер події в trace (з 0)
    kind: EventKind
    span: Optional[SourceSpan]       # де в тексті програми відбулась подія
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "event": self.kind.value,
            "span": asdict(self.span) if self.span else None,
            "data": self.data,
        }


class Trace:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[Event]:
        return iter(self._events)

    def __getitem__(self, i: int) -> Event:
        return self._events[i]

    def kinds(self) -> list[EventKind]:
        return [e.kind for e in self._events]

    def of(self, kind: EventKind) -> list[Event]:
        return [e for e in self._events if e.kind is kind]

    def to_list(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._events]

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_list(), ensure_ascii=False, indent=indent)
