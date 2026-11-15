"""python -m sipl.visualization program.sipl [--out out/tree] — експорт дерева виводу."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..source import SiplSyntaxError
from . import ParseTreeView, export_parse_tree


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sipl.visualization",
                                 description="Дерево синтаксичного виводу SIPL-програми")
    ap.add_argument("file", type=Path, help="файл з програмою SIPL")
    ap.add_argument("--out", type=Path, default=None,
                    help="базове ім'я вихідних файлів (.txt/.json/.dot/.svg)")
    args = ap.parse_args(argv)

    try:
        source = args.file.read_text(encoding="utf-8")
        view = ParseTreeView(source)
    except OSError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    except SiplSyntaxError as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 2

    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")
    print(view.to_text(), end="")
    if args.out:
        for path in export_parse_tree(source, args.out):
            print(f"[OK] {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
