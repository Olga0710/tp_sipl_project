"""Інтерпретатор SIPL: виконання AST над станом змінних із подієвою моделлю (CORE-03).

Стан — відображення змінна -> ціле число. Виконання генерує події (trace.py),
на які можна підписатися через listener (так працюватимуть debugger і візуалізатор).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Optional

from . import ast
from .parser import parse
from .source import Diagnostic, Position, SourceSpan
from .trace import Event, EventKind, Trace

DEFAULT_MAX_STEPS = 100_000
_UNKNOWN_SPAN = SourceSpan(Position(0, 1, 1), Position(0, 1, 1))


class SiplRuntimeError(Exception):
    """Помилка виконання з прив'язкою до місця в тексті програми."""

    def __init__(self, diagnostic: Diagnostic):
        super().__init__(str(diagnostic))
        self.diagnostic = diagnostic
        self.state: dict[str, int] = {}      
        self.trace: Optional[Trace] = None  


class StepLimitExceeded(SiplRuntimeError):
    """Перевищено ліміт кроків (ймовірно, нескінченний цикл)."""


@dataclass(frozen=True)
class RunResult:
    state: dict[str, int]
    steps: int
    trace: Trace


def _diag(message: str, node: ast.Node) -> Diagnostic:
    return Diagnostic(message, node.span or _UNKNOWN_SPAN)


class Interpreter:
    def __init__(
        self,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
        listener: Optional[Callable[[Event], None]] = None,
    ):
        self.max_steps = max_steps
        self._listener = listener
        self.state: dict[str, int] = {}
        self.steps = 0
        self.trace = Trace()

    # ---------- публічний API ----------
    def run(self, program: ast.Program, initial_state: Optional[Mapping[str, int]] = None) -> RunResult:
        self.state = dict(initial_state or {})
        self.steps = 0
        self.trace = Trace()
        self._emit(EventKind.PROGRAM_STARTED, program.span, state=dict(self.state))
        try:
            self._exec(program.body)
        except SiplRuntimeError as exc:
            self._emit(
                EventKind.EXECUTION_FAILED, exc.diagnostic.span,
                message=exc.diagnostic.message, state=dict(self.state),
            )
            exc.state = dict(self.state)
            exc.trace = self.trace
            raise
        self._emit(EventKind.PROGRAM_FINISHED, program.span, state=dict(self.state), steps=self.steps)
        return RunResult(dict(self.state), self.steps, self.trace)

    # ---------- події та кроки ----------
    def _emit(self, kind: EventKind, span: Optional[ast.SourceSpan], **data) -> None:
        event = Event(len(self.trace), kind, span, data)
        self.trace.append(event)
        if self._listener:
            self._listener(event)

    def _tick(self, node: ast.Node) -> None:
        """Один крок виконання; захист від нескінченних циклів."""
        self.steps += 1
        if self.steps > self.max_steps:
            raise StepLimitExceeded(_diag(
                f"Перевищено ліміт кроків ({self.max_steps}): можливий нескінченний цикл", node))

    def _before(self, node: ast.Stmt, kind: str) -> None:
        self._emit(EventKind.BEFORE_STATEMENT, node.span, statement=kind)

    def _after(self, node: ast.Stmt, kind: str) -> None:
        self._emit(EventKind.AFTER_STATEMENT, node.span, statement=kind, state=dict(self.state))

    # ---------- оператори ----------
    def _exec(self, node: ast.Stmt) -> None:
        while isinstance(node, ast.Seq):             
            self._exec(node.first)
            node = node.second

        if isinstance(node, ast.Assign):
            self._before(node, "assign")
            self._tick(node)
            value = self._eval(node.value)
            old = self.state.get(node.target)
            self.state[node.target] = value
            self._emit(EventKind.VARIABLE_CHANGED, node.span, name=node.target, old=old, new=value)
            self._after(node, "assign")

        elif isinstance(node, ast.Block):
            self._exec(node.body)

        elif isinstance(node, ast.If):
            self._before(node, "if")
            result = self._check(node.cond)
            self._exec(node.then if result else node.orelse)
            self._after(node, "if")

        elif isinstance(node, ast.While):
            self._before(node, "while")
            while self._check(node.cond):
                self._exec(node.body)
            self._after(node, "while")

        elif isinstance(node, ast.Skip):
            self._before(node, "skip")
            self._tick(node)
            self._after(node, "skip")

        else:
            raise TypeError(f"Невідомий вузол оператора: {type(node).__name__}")

    def _check(self, cond: ast.Cond) -> bool:
        """Обчислити умову оператора if/while: це окремий крок і окрема подія."""
        self._tick(cond)
        result = self._cond(cond)
        self._emit(EventKind.CONDITION_EVALUATED, cond.span, result=result)
        return result

    # ---------- вирази й умови ----------
    def _eval(self, node: ast.Expr) -> int:
        if isinstance(node, ast.Num):
            return node.value
        if isinstance(node, ast.Var):
            if node.name not in self.state:
                raise SiplRuntimeError(_diag(
                    f"Змінна '{node.name}' не має значення (не ініціалізована)", node))
            return self.state[node.name]
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left)
            right = self._eval(node.right)
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
        raise TypeError(f"Невідомий вузол виразу: {type(node).__name__}")

    def _cond(self, node: ast.Cond) -> bool:
        if isinstance(node, ast.Compare):
            left = self._eval(node.left)
            right = self._eval(node.right)
            return left == right if node.op == "=" else left > right
        if isinstance(node, ast.Or):
            left = self._cond(node.left)          
            right = self._cond(node.right)
            return left or right
        if isinstance(node, ast.Not):
            return not self._cond(node.operand)
        raise TypeError(f"Невідомий вузол умови: {type(node).__name__}")


def run(
    program: ast.Program,
    initial_state: Optional[Mapping[str, int]] = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    listener: Optional[Callable[[Event], None]] = None,
) -> RunResult:
    return Interpreter(max_steps=max_steps, listener=listener).run(program, initial_state)


def run_source(source: str, initial_state: Optional[Mapping[str, int]] = None, **options) -> RunResult:
    """Розібрати текст і виконати."""
    return run(parse(source), initial_state, **options)
