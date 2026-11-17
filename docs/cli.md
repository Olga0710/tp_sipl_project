# SIPL CLI

```
sipl КОМАНДА ФАЙЛ [параметри]
python -m sipl КОМАНДА ФАЙЛ [параметри]      # те саме без встановлення (PYTHONPATH=src)
```

`ФАЙЛ` — шлях до програми SIPL; `-` означає читання зі stdin. Кодування — UTF-8.

## Команди

| Команда | Що робить |
|---|---|
| `parse` | будує AST і виводить його (текст або JSON) |
| `check` | перевіряє синтаксис; показує вхідні змінні, які треба задати через `--set` |
| `run` | виконує програму й виводить кінцевий стан |
| `trace` | виконує програму й виводить послідовність подій виконання |
| `tree` | дерево синтаксичного виводу (parse tree): `--format text\|json\|dot\|svg`; листки пронумеровано в порядку обходу зліва направо (як на рис. 1 практикуму) |
| `sem` | семантичний терм програми в нотації курсу; `--steps` — послідовність застосованих правил |

## Параметри

| Параметр | Команди | Значення |
|---|---|---|
| `--json` | усі | вивід одним JSON-документом у stdout (і успіх, і помилки) |
| `--set ІМ'Я=ЧИСЛО` | `run`, `trace` | початкове значення змінної; можна повторювати |
| `--max-steps N` | `run`, `trace` | ліміт кроків (за замовчуванням 100000) |
| `--format F` | `tree` | `text` (за замовчуванням), `json`, `dot`, `svg` |
| `--style S` | `sem` | `course` (за замовчуванням), `ascii`, `latex` |
| `--steps` | `sem` | показати кроки: правила NS_Prog, NS_Stm_As, ... |
| `--out БАЗА` | `tree` | записати `БАЗА.txt/.json/.dot/.svg` замість виводу в консоль |
| `--version` | — | версія |

## Коди завершення

| Код | Значення |
|---|---|
| 0 | успіх |
| 1 | синтаксична помилка програми |
| 2 | помилка виконання (змінна без значення, перевищено ліміт кроків) |
| 3 | помилка використання або вводу/виводу (невірні аргументи, файл не знайдено) |

## Формат JSON (schema = 1)

Кожен документ має спільну «обгортку»:

```json
{ "schema": 1, "command": "run", "ok": true, ... }
```

Додаткові поля успішної відповіді:

| Команда | Поля |
|---|---|
| `parse` | `ast` — вкладений об'єкт: `{"node": "Assign", "target": "x", "value": {...}, "span": {...}}` |
| `check` | `inputs` — список імен |
| `run` | `state` — `{ім'я: число}`, `steps` — кількість кроків |
| `trace` | `state`, `steps`, `trace` — список подій |
| `tree` | `tree` — дерево виводу; з `--out` замість нього `files` |
| `sem` | `style`, `text` — запис терму, `term` — структура терму, `steps` (з `--steps`) — список `{index, rule, lhs, rhs}` |

Подія trace:

```json
{ "index": 2, "event": "VariableChanged", "span": {"start": {...}, "end": {...}},
  "data": {"name": "x", "old": null, "new": 1} }
```

Види подій: `ProgramStarted`, `BeforeStatement`, `ConditionEvaluated`, `VariableChanged`,
`AfterStatement`, `ProgramFinished`, `ExecutionFailed`.

`span` — діапазон у тексті: `{"start": {"offset", "line", "column"}, "end": {...}}`;
рядок і колонка нумеруються з 1, кінець не включається.

Помилка (`ok: false`):

```json
{ "schema": 1, "command": "run", "ok": false,
  "error": {"kind": "runtime", "message": "...", "span": {...}},
  "state": {} }
```

`kind`: `syntax`, `runtime`, `step_limit`, `usage`, `io`. Для `runtime`/`step_limit` додатково є
`state` (стан у момент помилки), а для `trace` — ще й `trace` (події до помилки).
`span` дорівнює `null`, якщо помилка не пов'язана з місцем у тексті.

## Приклади

```
sipl check examples/euclid.sipl
sipl run examples/euclid.sipl --set M=12 --set N=18          # M = 6, N = 6
sipl trace examples/power.sipl --set X=2 --set Y=3
sipl run examples/euclid.sipl --set M=12 --set N=18 --json
sipl tree examples/euclid.sipl --format svg > euclid.svg
sipl tree examples/euclid.sipl --out out/euclid
sipl sem examples/power.sipl --steps                        # терм і його побудова за правилами курсу
```
