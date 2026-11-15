# Демонстраційний сценарій захисту

Програми з папки `demo/` **не використовуються в тестах** — це «нові приклади» з критерію приймання №1.
Усі виводи нижче отримано реальним запуском (команди з кореня проєкту, `sipl` встановлено через `pip install -e ".[dev]"`).

Орієнтовний хід (5–7 хв): пп. 1–2 (чи працює), 4 (trace), 5 (parse tree), 6 (семантика), 7–8 (помилки й межі), 9 (JSON).
Під час захисту корисно змінити вхідні значення на ті, що попросить викладач.

### 1. Цілочисельне ділення (x div y, x mod y через + та −)

```
> sipl check demo/divide.sipl
OK: програма синтаксично коректна
Вхідні змінні (задайте через --set): X, Y
```

**Що сказати:** `check` перевіряє синтаксис і підказує, які змінні треба задати: вхідні — ті, що можуть бути прочитані до присвоєння.

```
> sipl run demo/divide.sipl --set X=17 --set Y=5
Q = 3
X = 2
Y = 5
```

**Що сказати:** 17 div 5 = 3 у `Q`, залишок 2 лишився в `X`. Програми немає в жодному тесті — інструмент працює на класі програм.

### 2. Факторіал

```
> sipl run demo/factorial.sipl --set N=5
F = 120
N = 1
```

**Що сказати:** 5! = 120.

### 3. Парність і пріоритет `;`

```
> sipl run demo/parity.sipl --set N=7
E = 0
N = 1
```

**Що сказати:** `while N > 1 do N := N - 2; if …` — тіло циклу це один оператор, `;` має найнижчий пріоритет (домовленість №2 у специфікації).

```
> sipl run demo/parity.sipl --set N=10
E = 1
N = 0
```

**Що сказати:** Парне число: `E = 1`.

### 4. Trace виконання (події)

```
> sipl trace demo/parity.sipl --set N=3
#0   ProgramStarted     1:1-4:4
#1   BeforeStatement    2:3-2:28     while
#2   ConditionEvaluated 2:9-2:14     результат = True
#3   BeforeStatement    2:18-2:28    assign
#4   VariableChanged    2:18-2:28    N: 3 -> 1
#5   AfterStatement     2:18-2:28    assign
#6   ConditionEvaluated 2:9-2:14     результат = False
#7   AfterStatement     2:3-2:28     while
#8   BeforeStatement    3:3-3:35     if
#9   ConditionEvaluated 3:6-3:11     результат = False
#10  BeforeStatement    3:29-3:35    assign
#11  VariableChanged    3:29-3:35    E: None -> 0
#12  AfterStatement     3:29-3:35    assign
#13  AfterStatement     3:3-3:35     if
#14  ProgramFinished    1:1-4:4      кроків: 5
```

**Що сказати:** Видно `BeforeStatement/AfterStatement`, кожну перевірку умови з результатом і зміну змінної `старе -> нове`. Це основа для debugger.

### 5. Дерево синтаксичного виводу з нумерацією листків

```
> sipl tree demo/parity.sipl
<програма> [NP1]  1:1-4:4
├── [1] begin  1:1-1:6
├── <оператор> [NS2]  2:3-3:35
│   ├── <оператор> [NS4]  2:3-2:28
│   │   ├── [2] while  2:3-2:8
│   │   ├── <умова> [NB2]  2:9-2:14
│   │   │   ├── <вираз> [NA2]  2:9-2:10
│   │   │   │   └── <змінна> [NV]  2:9-2:10
│   │   │   │       └── [3] N  2:9-2:10
│   │   │   ├── [4] >  2:11-2:12
…

Обхід листків зліва направо: 1 begin 2 while 3 N 4 > 5 1 6 do 7 N 8 := 9 N 10 - 11 2 12 ; 13 if 14 N 15 = 16 0 17 then 18 E 19 := 20 1 21 else 22 E 23 := 24 0 25 end
```

**Що сказати:** кожен вузол — правило БНФ курсу (NS4, NB2, NA2 …) і діапазон у тексті. Листки пронумеровано в порядку обходу зліва направо, як на рис. 1 практикуму; останній рядок — програма, прочитана з листків. Збіг із початковою програмою і є перевіркою синтаксичної коректності. Малюнок: `sipl tree demo/parity.sipl --out out/parity` (файл `.svg`, номери червоні).

### 6. Семантичний терм і порядок застосування правил

```
> sipl sem demo/factorial.sipl --steps
AS^F(1̄) · WH(S²(gr, N⇒, 1̄), AS^F(S²(mult, F⇒, N⇒)) · AS^N(S²(sub, N⇒, 1̄)))

  1. [NS_Prog] sem_P(begin F := 1; while N > 1 do begin F := F * N; N := N - 1 end end) = sem_S(F := 1; while N > 1 do begin F := F * N; N := N - 1 end)
  2. [NS_Stm_Seq] sem_S(F := 1; while N > 1 do begin F := F * N; N := N - 1 end) = sem_S(F := 1) · sem_S(while N > 1 do begin F := F * N; N := N - 1 end)
  3. [NS_Stm_As] sem_S(F := 1) = AS^F(sem_A(1))
  4. [NS_A_Num] sem_A(1) = 1̄
  5. [NS_Stm_Wh] sem_S(while N > 1 do begin F := F * N; N := N - 1 end) = WH(sem_B(N > 1), sem_S(begin F := F * N; N := N - 1 end))
  6. [NS_B_gr] sem_B(N > 1) = S²(gr, sem_A(N), sem_A(1))
  7. [NS_A_Var] sem_A(N) = N⇒
  8. [NS_A_Num] sem_A(1) = 1̄
  9. [NS_Stm_BE] sem_S(begin F := F * N; N := N - 1 end) = sem_S(F := F * N; N := N - 1)
 10. [NS_Stm_Seq] sem_S(F := F * N; N := N - 1) = sem_S(F := F * N) · sem_S(N := N - 1)
 11. [NS_Stm_As] sem_S(F := F * N) = AS^F(sem_A(F * N))
 12. [NS_A_Mult] sem_A(F * N) = S²(mult, sem_A(F), sem_A(N))
…
```

**Що сказати:** Терм побудований рекурсивно за правилами NS_Prog, NS_Stm_Seq, NS_Stm_Wh … у тому ж порядку, що й у посібнику.

### 7. Помилка синтаксису з позицією

```
> sipl check demo/broken.sipl
demo/broken.sipl:4:5: помилка: Очікувалося 'do', а знайдено 'S'
  4 |     S := S + N;
    |     ^
```
Код завершення: **1**.

**Що сказати:** Пропущено `do`: помилка вказує рядок, колонку та місце під `^`. Код завершення 1.

### 8. Нескінченний цикл

```
> sipl run demo/forever.sipl --max-steps 1000
demo/forever.sipl:3:18: помилка виконання: Перевищено ліміт кроків (1000): можливий нескінченний цикл
  3 |   while X > 0 do X := X + 1
    |                  ^^^^^^^^^^
```
Код завершення: **2**.

**Що сказати:** Ліміт кроків зупиняє програму. Код завершення 2 (помилка виконання). Нерозв'язність проблеми зупинки — межа автоматизації.

### 9. Те саме у форматі JSON для інтеграцій

```
> sipl run demo/divide.sipl --set X=17 --set Y=5 --json
{
  "schema": 1,
  "command": "run",
  "ok": true,
  "state": {
    "X": 2,
    "Y": 5,
    "Q": 3
  },
  "steps": 11
}
```

**Що сказати:** Стабільна схема: `schema`, `command`, `ok`; з неї працюватимуть IDE чи веб-інтерфейс.
