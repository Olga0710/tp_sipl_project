"""Командний рядок SIPL: parse, check, run, trace, tree, sem (CORE-05).

Коди завершення:  0 — успіх;  1 — синтаксична помилка;  2 — помилка виконання
(в т.ч. перевищено ліміт кроків);  3 — помилка використання або вводу/виводу.
У режимі --json усе (і помилки) виводиться в stdout як один JSON-документ.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from . import __version__
from .ast_format import ast_to_dict, ast_to_text, input_variables
from .interpreter import DEFAULT_MAX_STEPS, SiplRuntimeError, StepLimitExceeded, run
from .parser import parse
from .semantics import STYLES, format_term, semantic_term, term_to_dict
from .source import Diagnostic, SiplSyntaxError
from .trace import Event, EventKind
from .visualization import ParseTreeView, export_parse_tree
from .visualization.parse_tree_view import span_str

EXIT_OK, EXIT_SYNTAX, EXIT_RUNTIME, EXIT_USAGE = 0, 1, 2, 3
SCHEMA_VERSION = 1


class _UsageError(Exception):
    pass


class _ArgParser(argparse.ArgumentParser):
    def error(self, message: str):                           
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: помилка: {message}\n")


#  побудова парсера аргументів
def build_parser() -> argparse.ArgumentParser:
    parser = _ArgParser(prog="sipl", description="SIPL Language Toolkit")
    parser.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="КОМАНДА")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("file", help="файл з програмою SIPL ('-' — читати зі stdin)")
    common.add_argument("--json", action="store_true", help="вивід у форматі JSON (для інтеграцій)")

    run_opts = argparse.ArgumentParser(add_help=False)
    run_opts.add_argument("--set", dest="assignments", action="append", default=[], metavar="ІМ'Я=ЧИСЛО",
                          help="початкове значення змінної (можна повторювати)")
    run_opts.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS, metavar="N",
                          help=f"ліміт кроків виконання (за замовчуванням {DEFAULT_MAX_STEPS})")

    sub.add_parser("parse", parents=[common], help="побудувати AST")
    sub.add_parser("check", parents=[common], help="перевірити синтаксис і показати вхідні змінні")
    sub.add_parser("run", parents=[common, run_opts], help="виконати програму, показати кінцевий стан")
    sub.add_parser("trace", parents=[common, run_opts], help="виконати програму, показати trace подій")
    p_tree = sub.add_parser("tree", parents=[common], help="дерево синтаксичного виводу (VIS-01)")
    p_tree.add_argument("--format", choices=["text", "json", "dot", "svg"], default="text",
                        help="формат виводу (за замовчуванням text)")
    p_tree.add_argument("--out", metavar="БАЗА",
                        help="записати БАЗА.txt/.json/.dot/.svg замість виводу в консоль")
    p_sem = sub.add_parser("sem", parents=[common], help="семантичний терм програми (SEM-01)")
    p_sem.add_argument("--style", choices=list(STYLES), default="course",
                       help="запис терму: course (за замовчуванням), ascii, latex")
    p_sem.add_argument("--steps", action="store_true",
                       help="показати послідовність застосованих правил sem_P/sem_S/sem_A/sem_B")
    return parser


# допоміжні
def _force_utf8() -> None:
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def _read_source(name: str) -> str:
    if name == "-":
        return sys.stdin.read()
    return Path(name).read_text(encoding="utf-8")


def _parse_assignments(items: list[str]) -> dict[str, int]:
    state: dict[str, int] = {}
    for item in items:
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)=(-?\d+)", item.strip())
        if not match:
            raise _UsageError(f"Некоректне --set '{item}': очікується ІМ'Я=ЧИСЛО, наприклад X=5")
        state[match.group(1)] = int(match.group(2))
    return state


def _envelope(command: str, ok: bool, **fields: Any) -> dict[str, Any]:
    return {"schema": SCHEMA_VERSION, "command": command, "ok": ok, **fields}


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _error_dict(kind: str, message: str, diagnostic: Optional[Diagnostic] = None) -> dict[str, Any]:
    span = None
    if diagnostic is not None:
        from dataclasses import asdict
        span = asdict(diagnostic.span)
    return {"kind": kind, "message": message, "span": span}


def format_diagnostic(source: str, diagnostic: Diagnostic, filename: str, kind: str = "помилка") -> str:
    """Рядок помилки з фрагментом коду та вказівником."""
    start, end = diagnostic.span.start, diagnostic.span.end
    lines = source.splitlines()
    text = lines[start.line - 1] if 0 < start.line <= len(lines) else ""
    width = end.column - start.column if end.line == start.line and end.column > start.column else 1
    number = str(start.line)
    pad = " " * len(number)
    return (
        f"{filename}:{start.line}:{start.column}: {kind}: {diagnostic.message}\n"
        f"  {number} | {text}\n"
        f"  {pad} | {' ' * (start.column - 1)}{'^' * width}\n"
    )


def format_event(event: Event) -> str:
    d = event.data
    if event.kind is EventKind.VARIABLE_CHANGED:
        detail = f"{d['name']}: {d['old']} -> {d['new']}"
    elif event.kind is EventKind.CONDITION_EVALUATED:
        detail = f"результат = {d['result']}"
    elif event.kind in (EventKind.BEFORE_STATEMENT, EventKind.AFTER_STATEMENT):
        detail = d["statement"]
    elif event.kind is EventKind.PROGRAM_FINISHED:
        detail = f"кроків: {d['steps']}"
    elif event.kind is EventKind.EXECUTION_FAILED:
        detail = d["message"]
    else:
        detail = ""
    span = span_str(event.span) if event.span else "-"
    return f"#{event.index:<3} {event.kind.value:<18} {span:<12} {detail}".rstrip()


def _state_lines(state: dict[str, int]) -> str:
    return "".join(f"{name} = {value}\n" for name, value in sorted(state.items()))


#  команди
def _cmd_parse(args, source: str) -> int:
    program = parse(source)
    if args.json:
        _print_json(_envelope("parse", True, ast=ast_to_dict(program)))
    else:
        print(ast_to_text(program), end="")
    return EXIT_OK


def _cmd_check(args, source: str) -> int:
    program = parse(source)
    inputs = input_variables(program)
    if args.json:
        _print_json(_envelope("check", True, inputs=inputs))
    else:
        print("OK: програма синтаксично коректна")
        if inputs:
            print("Вхідні змінні (задайте через --set): " + ", ".join(inputs))
    return EXIT_OK


def _execute(args, source: str, command: str) -> int:
    program = parse(source)
    initial = _parse_assignments(args.assignments)
    want_trace = command == "trace"
    try:
        result = run(program, initial, max_steps=args.max_steps)
    except SiplRuntimeError as exc:
        kind = "step_limit" if isinstance(exc, StepLimitExceeded) else "runtime"
        if args.json:
            extra = {"trace": exc.trace.to_list()} if want_trace and exc.trace else {}
            _print_json(_envelope(command, False, error=_error_dict(kind, exc.diagnostic.message, exc.diagnostic),
                                  state=exc.state, **extra))
        else:
            if want_trace and exc.trace:
                for event in exc.trace:
                    print(format_event(event))
            print(format_diagnostic(source, exc.diagnostic, _filename(args), "помилка виконання"),
                  end="", file=sys.stderr)
        return EXIT_RUNTIME

    if args.json:
        extra = {"trace": result.trace.to_list()} if want_trace else {}
        _print_json(_envelope(command, True, state=result.state, steps=result.steps, **extra))
    elif want_trace:
        for event in result.trace:
            print(format_event(event))
    else:
        print(_state_lines(result.state), end="")
    return EXIT_OK


def _cmd_run(args, source: str) -> int:
    return _execute(args, source, "run")


def _cmd_trace(args, source: str) -> int:
    return _execute(args, source, "trace")


def _cmd_tree(args, source: str) -> int:
    view = ParseTreeView(source)
    if args.out:
        paths = [str(p) for p in export_parse_tree(source, args.out)]
        if args.json:
            _print_json(_envelope("tree", True, files=paths))
        else:
            for p in paths:
                print(f"[OK] {p}")
        return EXIT_OK
    if args.json:
        _print_json(_envelope("tree", True, tree=view.to_dict()))
    elif args.format == "json":
        print(view.to_json())
    elif args.format == "dot":
        print(view.to_dot(), end="")
    elif args.format == "svg":
        print(view.to_svg(), end="")
    else:
        print(view.to_text(), end="")
    return EXIT_OK


def _cmd_sem(args, source: str) -> int:
    result = semantic_term(source)
    text = format_term(result.term, args.style)
    if args.json:
        payload = _envelope("sem", True, style=args.style, text=text, term=term_to_dict(result.term))
        if args.steps:
            payload["steps"] = [step.to_dict() for step in result.steps]
        _print_json(payload)
    else:
        print(text)
        if args.steps:
            print()
            for step in result.steps:
                print(f"{step.index:>3}. [{step.rule}] {step.lhs} = {step.rhs}")
    return EXIT_OK


_COMMANDS = {"parse": _cmd_parse, "check": _cmd_check, "run": _cmd_run, "trace": _cmd_trace,
             "tree": _cmd_tree, "sem": _cmd_sem}


def _filename(args) -> str:
    return "<stdin>" if args.file == "-" else args.file


def _fail(args, kind: str, message: str, code: int, diagnostic: Optional[Diagnostic] = None,
          source: str = "") -> int:
    if args.json:
        _print_json(_envelope(args.command, False, error=_error_dict(kind, message, diagnostic)))
    elif diagnostic is not None:
        print(format_diagnostic(source, diagnostic, _filename(args)), end="", file=sys.stderr)
    else:
        print(f"Помилка: {message}", file=sys.stderr)
    return code


# - точка входу
def main(argv: Optional[list[str]] = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)
    try:
        source = _read_source(args.file)
    except OSError as exc:
        return _fail(args, "io", f"Не вдалося прочитати '{args.file}': {exc.strerror or exc}", EXIT_USAGE)
    try:
        return _COMMANDS[args.command](args, source)
    except SiplSyntaxError as exc:
        return _fail(args, "syntax", exc.diagnostic.message, EXIT_SYNTAX, exc.diagnostic, source)
    except _UsageError as exc:
        return _fail(args, "usage", str(exc), EXIT_USAGE)


if __name__ == "__main__":
    sys.exit(main())
