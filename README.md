# SIPL Language Toolkit

[![CI](https://github.com/Olga0710/tp_sipl_project/actions/workflows/ci.yml/badge.svg)](https://github.com/Olga0710/tp_sipl_project/actions/workflows/ci.yml)

Інструменти для навчальної мови програмування **SIPL** (SImple Programming Language) з курсу
«Теорія програмування»: парсер, інтерпретатор із trace, візуалізація дерева виводу, семантичні терми
та CLI. Спільне ядро — бібліотека `sipl`; CLI та інші клієнти використовують його API.

## Заявлені завдання курсового проєкту

| ID | Завдання | Бали | Де реалізовано |
|---|---|---|---|
| CORE-01 | Формальна специфікація SIPL | 0.5 | `grammar/sipl.ebnf`, `tests/test_parser.py` (15 коректних і 20 некоректних програм) |
| CORE-02 | Парсер і типізоване AST зі `SourceSpan` | 1.5 | `lexer.py`, `parser.py`, `ast.py`, `parse_tree.py`, `ast_builder.py`, `source.py` |
| CORE-03 | Інтерпретатор | 2.0 | `interpreter.py` (стан, `;`, `if`, `while`, `begin/end`, `skip`, ліміт кроків) |
| CORE-04 | Подієва модель і trace | 1.0 | `trace.py`, команда `sipl trace` (+ `--json`) |
| CORE-05 | CLI: parse, check, run, trace + JSON | 1.0 | `cli.py`, `docs/cli.md`, `tests/test_cli.py` |
| VIS-01 | Візуалізація дерева синтаксичного виводу | 1.5 | `visualization/` (text, JSON, DOT, SVG), `sipl tree` |
| SEM-01 | Семантичний терм програми | 2.0 | `semantics/`, `sipl sem`, `tests/test_semantics.py` |
| REL-01 | CI | 0.5 | `.github/workflows/ci.yml` |
| REL-02 | GitHub Releases + SemVer + CHANGELOG | 0.5 | `CHANGELOG.md`, `.github/workflows/release.yml`, тег `v0.5.0` |

Сума заявлених завдань: 10.5.

## Встановлення

Потрібен Python 3.10 або новіший.

```
git clone https://github.com/Olga0710/tp_sipl_project.git
cd <REPO>
python -m venv env
env\Scripts\activate            
pip install -e ".[dev]"
```

Після цього доступна команда `sipl` (також `python -m sipl`).

## Швидкий старт

```
sipl check examples/euclid.sipl                              # синтаксис + вхідні змінні
sipl run   examples/euclid.sipl --set M=12 --set N=18        # M = 6, N = 6
sipl trace examples/power.sipl  --set X=2 --set Y=3          # події виконання
sipl tree  examples/euclid.sipl --out out/euclid             # .txt .json .dot .svg
sipl sem   examples/power.sipl --steps                       # семантичний терм і правила
sipl run   examples/euclid.sipl --set M=12 --set N=18 --json # JSON для інтеграцій
```

Повний опис команд, кодів завершення та формату JSON — у [docs/cli.md](docs/cli.md).

## Приклад програми

```
begin
  R := 1;
  while Y > 0 do
  begin
    R := R * X;
    Y := Y - 1
  end
end
```

Семантичний терм цієї програми (`sipl sem examples/power.sipl`):

```
AS^R(1̄) · WH(S²(gr, Y⇒, 0̄), AS^R(S²(mult, R⇒, X⇒)) · AS^Y(S²(sub, Y⇒, 1̄)))
```

Приклади: `examples/euclid.sipl`, `examples/power.sipl`, `examples/nested.sipl`.

## Архітектура

```
text ──lexer──▶ tokens ──parser──▶ parse tree (ParseNode, правила NP1…NB5)
                                        │
                                  ast_builder
                                        ▼
                                      AST (ast.py, SourceSpan)
                    ┌───────────────────┼──────────────────────┐
                    ▼                   ▼                      ▼
           interpreter + trace   semantics (терм)     visualization (parse tree)
                    └───────────────────┴──────────────────────┘
                                        ▼
                                   cli.py / JSON
```

Лексер, парсер, AST, виконання, семантика та візуалізація — бібліотека; CLI є лише клієнтом.

## Мова SIPL: домовленості та розширення

Граматика відповідає БНФ практикуму (NP1, NS1–NS6, NA1–NA6, NB1–NB5). БНФ неоднозначна, тому зафіксовано:

- `;` має найнижчий пріоритет і групується праворуч; тіло `while` та гілки `if` — один оператор (для кількох — `begin … end`);
- `*` сильніше за `+` та `−`, які лівоасоціативні; `¬` сильніше за `∨`;
- програма завжди має вигляд `begin … end`; `if` завжди має гілку `else`;
- дужки навколо умови та виразу розрізняються за токеном після закритої дужки.

Розширення відносно БНФ курсу: змінна — ідентифікатор (літери, цифри, `_`); `or`/`not` — синоніми `∨`/`¬`.

## Тестування

```
pytest --cov=sipl --cov-report=term-missing
ruff check .
mypy
```

## Обмеження

- Нескінченні цикли виявляються лише за лімітом кроків (проблема зупинки нерозв'язна).
- Читання змінної без значення — помилка виконання; значення задаються через `--set`.
- `∨` обчислює обидва операнди; ділення, `<` та `∧` не входять до SIPL.
- Інструмент не доводить коректність програм і не обчислює семантичні терми поза тестами (це окремі завдання каталогу).

demo update

