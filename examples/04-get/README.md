# 04 — `ds get`

Свёртка журнала в состояние источника (Level 1: последняя запись по `(dt, cnt)` на каждую пару
`показатель × id`). Грузятся те же два батча, что в [`01-basic-load`](../01-basic-load/).

## Запуск

```bash
bash run.sh /tmp/ex04
```

Выводит две выгрузки:

1. `ds get --dt 1706745600` — состояние на 2024-02-01, все показатели:
   - `102.email` = `bob.new@example.com` (POST из второго батча победил);
   - `103.phone` = `null` (DELETE из первого батча остаётся явной записью);
   - у `104` нет ключа `phone` — пары `(phone, 104)` не было ни в одной транзакции.
2. `ds get --dt 1704067200 --lb email` — «машина времени» на 2024-01-01, только `email`:
   - `102.email` = `bob@example.com` (второй батч ещё не наступил по `dt`);
   - `104` отсутствует целиком (его батч — позже среза).

## Формат вывода

`{meta, data}` на источник. `data` — широкая таблица: строка на `id`, колонки — ключевой
показатель + выбранные показатели. `meta.gen_max_cnt` — макс. `cnt`, попавший в срез.

Разбор — [`../../docs/reference/get-output-format.md`](../../docs/reference/get-output-format.md),
[`../../docs/reference/cli.md`](../../docs/reference/cli.md),
[`../../docs/explanation/single-source-fold.md`](../../docs/explanation/single-source-fold.md).

> `expected/stdout.txt`: поле `generated_at` (реальное время генерации) в тестовом прогоне
> нормализуется в `0` — оно недетерминированно.
