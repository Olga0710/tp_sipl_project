"""CORE-05: інтеграційні тести CLI (виклик main() та справжній процес)."""
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

from sipl import __version__
from sipl.cli import SCHEMA_VERSION, format_diagnostic, main
from sipl.parser import parse_tree
from sipl.source import Diagnostic, Position, SourceSpan

ROOT = Path(__file__).resolve().parent.parent
EUCLID = "begin\n  while ¬ M = N do\n    if M > N then M := M - N\n    else N := N - M\nend\n"
LOOP = "begin while 1 = 1 do skip end\n"


def cli(*argv, stdin=None):
    """Виклик main(); повертає (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(list(argv))
            except SystemExit as exc:
                code = exc.code
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()


def write(tmp_path, text, name="program.sipl"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


# ---------------- check ----------------
def test_check_ok_text(tmp_path):
    code, out, _ = cli("check", write(tmp_path, EUCLID))
    assert code == 0 and "OK" in out
    assert "M, N" in out                                   # вхідні змінні


def test_check_ok_json_lists_inputs(tmp_path):
    code, out, _ = cli("check", write(tmp_path, EUCLID), "--json")
    data = json.loads(out)
    assert code == 0
    assert data == {"schema": SCHEMA_VERSION, "command": "check", "ok": True, "inputs": ["M", "N"]}


def test_check_syntax_error_text_has_position_and_caret(tmp_path):
    path = write(tmp_path, "begin\n  x := 1 +\nend\n")
    code, out, err = cli("check", path)
    assert code == 1 and out == ""
    assert f"{path}:3:1: помилка:" in err
    assert "^^^" in err and "3 | end" in err


def test_check_syntax_error_json(tmp_path):
    code, out, err = cli("check", write(tmp_path, "begin\n  x := 1 +\nend\n"), "--json")
    data = json.loads(out)
    assert code == 1 and err == ""
    assert data["ok"] is False and data["error"]["kind"] == "syntax"
    assert data["error"]["span"]["start"]["line"] == 3
    assert "вираз" in data["error"]["message"]


# ---------------- parse ----------------
def test_parse_json_contains_ast(tmp_path):
    code, out, _ = cli("parse", write(tmp_path, "begin x := 1 end"), "--json")
    data = json.loads(out)
    assert code == 0 and data["command"] == "parse" and data["ok"] is True
    assert data["ast"]["node"] == "Program" and data["ast"]["body"]["target"] == "x"


def test_parse_text_prints_tree(tmp_path):
    code, out, _ = cli("parse", write(tmp_path, "begin x := 1 end"))
    assert code == 0 and "Program" in out and "Assign x :=" in out


# ---------------- run ----------------
def test_run_text_with_set(tmp_path):
    code, out, _ = cli("run", write(tmp_path, EUCLID), "--set", "M=12", "--set", "N=18")
    assert code == 0 and out == "M = 6\nN = 6\n"


def test_run_json(tmp_path):
    code, out, _ = cli("run", write(tmp_path, EUCLID), "--set", "M=12", "--set", "N=18", "--json")
    data = json.loads(out)
    assert code == 0 and data["state"] == {"M": 6, "N": 6} and data["steps"] > 0
    assert set(data) == {"schema", "command", "ok", "state", "steps"}


def test_run_negative_initial_value(tmp_path):
    code, out, _ = cli("run", write(tmp_path, "begin y := x * 2 end"), "--set", "x=-4")
    assert code == 0 and "y = -8" in out


def test_run_uninitialized_variable_exit_2_text(tmp_path):
    path = write(tmp_path, EUCLID)
    code, out, err = cli("run", path)
    assert code == 2 and out == ""
    assert "помилка виконання" in err and "'M'" in err and "^" in err


def test_run_uninitialized_variable_json(tmp_path):
    code, out, _ = cli("run", write(tmp_path, EUCLID), "--json")
    data = json.loads(out)
    assert code == 2 and data["ok"] is False
    assert data["error"]["kind"] == "runtime" and data["error"]["span"] is not None
    assert data["state"] == {}


def test_run_step_limit(tmp_path):
    code, out, _ = cli("run", write(tmp_path, LOOP), "--max-steps", "100", "--json")
    data = json.loads(out)
    assert code == 2 and data["error"]["kind"] == "step_limit"
    assert "100" in data["error"]["message"]


def test_run_syntax_error_exit_1(tmp_path):
    code, _, err = cli("run", write(tmp_path, "begin x := end"))
    assert code == 1 and "помилка" in err


def test_run_bad_set_is_usage_error(tmp_path):
    path = write(tmp_path, "begin skip end")
    code, _, err = cli("run", path, "--set", "x")
    assert code == 3 and "ІМ'Я=ЧИСЛО" in err
    code, out, _ = cli("run", path, "--set", "x=abc", "--json")
    assert code == 3 and json.loads(out)["error"]["kind"] == "usage"


# ---------------- trace ----------------
def test_trace_json_events(tmp_path):
    code, out, _ = cli("trace", write(tmp_path, "begin x := 1 end"), "--json")
    data = json.loads(out)
    kinds = [e["event"] for e in data["trace"]]
    assert code == 0
    assert kinds == ["ProgramStarted", "BeforeStatement", "VariableChanged",
                     "AfterStatement", "ProgramFinished"]
    assert data["state"] == {"x": 1} and data["steps"] == 1


def test_trace_text_is_readable(tmp_path):
    code, out, _ = cli("trace", write(tmp_path, "begin x := 1 end"))
    assert code == 0
    assert "VariableChanged" in out and "x: None -> 1" in out
    assert "кроків: 1" in out


def test_trace_text_shows_condition_results(tmp_path):
    _, out, _ = cli("trace", write(tmp_path, "begin while x > 0 do x := x - 1 end"), "--set", "x=1")
    assert "результат = True" in out and "результат = False" in out


def test_trace_json_on_failure_keeps_events_and_error(tmp_path):
    code, out, _ = cli("trace", write(tmp_path, "begin x := y end"), "--json")
    data = json.loads(out)
    assert code == 2 and data["ok"] is False
    assert data["trace"][-1]["event"] == "ExecutionFailed"
    assert data["error"]["kind"] == "runtime"


def test_trace_text_on_failure_prints_events_then_error(tmp_path):
    code, out, err = cli("trace", write(tmp_path, "begin x := y end"))
    assert code == 2 and "ExecutionFailed" in out and "помилка виконання" in err


# ---------------- tree ----------------
def test_tree_text_default(tmp_path):
    code, out, _ = cli("tree", write(tmp_path, EUCLID))
    assert code == 0 and out.startswith("<програма> [NP1]")


def test_tree_formats(tmp_path):
    path = write(tmp_path, EUCLID)
    assert cli("tree", path, "--format", "dot")[1].startswith("digraph")
    assert cli("tree", path, "--format", "svg")[1].startswith("<svg")
    assert json.loads(cli("tree", path, "--format", "json")[1])["rule"] == "NP1"


def test_tree_json_envelope(tmp_path):
    code, out, _ = cli("tree", write(tmp_path, EUCLID), "--json")
    data = json.loads(out)
    assert code == 0 and data["command"] == "tree" and data["tree"]["symbol"] == "<програма>"


def test_tree_out_writes_files(tmp_path):
    base = str(tmp_path / "out" / "tree")
    code, out, _ = cli("tree", write(tmp_path, EUCLID), "--out", base)
    assert code == 0 and out.count("[OK]") == 4
    assert (tmp_path / "out" / "tree.svg").read_text(encoding="utf-8").startswith("<svg")


# ---------------- загальне ----------------
def test_missing_file_is_io_error(tmp_path):
    code, _, err = cli("check", str(tmp_path / "nope.sipl"))
    assert code == 3 and "Не вдалося прочитати" in err
    code, out, _ = cli("check", str(tmp_path / "nope.sipl"), "--json")
    assert code == 3 and json.loads(out)["error"]["kind"] == "io"


def test_reads_program_from_stdin():
    code, out, _ = cli("run", "-", stdin="begin x := 7 end")
    assert code == 0 and out == "x = 7\n"


def test_stdin_syntax_error_names_stdin():
    code, _, err = cli("check", "-", stdin="begin x := end")
    assert code == 1 and "<stdin>:1:" in err


def test_no_command_is_usage_error():
    code, _, err = cli()
    assert code == 3 and "sipl" in err


def test_unknown_command_is_usage_error():
    assert cli("frobnicate", "x")[0] == 3


def test_version_flag():
    code, out, _ = cli("--version")
    assert code == 0 and out.strip() == f"sipl {__version__}"


def test_every_json_output_has_the_common_envelope(tmp_path):
    path = write(tmp_path, "begin x := 1 end")
    for command in ("parse", "check", "run", "trace", "tree"):
        data = json.loads(cli(command, path, "--json")[1])
        assert data["schema"] == SCHEMA_VERSION and data["command"] == command and data["ok"] is True


def test_format_diagnostic_underlines_the_span():
    span = SourceSpan(Position(6, 1, 7), Position(9, 1, 10))
    text = format_diagnostic("begin foo end", Diagnostic("тест", span), "f.sipl")
    lines = text.splitlines()
    assert lines[0] == "f.sipl:1:7: помилка: тест"
    assert lines[1] == "  1 | begin foo end"
    assert lines[2] == "    |       ^^^"


def test_format_diagnostic_at_end_of_text_does_not_crash():
    p = Position(5, 3, 1)
    text = format_diagnostic("a\nb", Diagnostic("кінець", SourceSpan(p, p)), "f.sipl")
    assert "f.sipl:3:1" in text


# ---------------- справжній процес: коди завершення ----------------
def process(*argv):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "sipl", *argv], capture_output=True,
                          text=True, encoding="utf-8", env=env, cwd=ROOT)


def test_process_exit_codes_and_utf8_output():
    ok = process("run", "examples/power.sipl", "--set", "X=2", "--set", "Y=10")
    assert ok.returncode == 0 and "R = 1024" in ok.stdout
    tree = process("tree", "examples/euclid.sipl")
    assert tree.returncode == 0 and "<оператор>" in tree.stdout


def test_process_error_exit_codes(tmp_path):
    bad = write(tmp_path, "begin x := end")
    assert process("check", bad).returncode == 1
    assert process("run", "examples/euclid.sipl").returncode == 2
    assert process("check", str(tmp_path / "missing.sipl")).returncode == 3
    assert process().returncode == 3


def test_package_version_matches_pyproject():
    try:
        import tomllib
    except ModuleNotFoundError:                            
        return
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == __version__


def test_example_programs_are_valid_sipl():
    for path in sorted((ROOT / "examples").glob("*.sipl")):
        parse_tree(path.read_text(encoding="utf-8"))
