# Быстрый старт

За 5 минут: установить `ds`, создать источник, загрузить два батча, посмотреть результат.
Это обучающий сценарий — детальный разбор в [`loading-data.md`](loading-data.md).

## 1. Установка

Зависимостей, кроме стандартной библиотеки Python (3.9+), нет.

```bash
pip install -e .
```

Появится команда `ds`. Без установки — `PYTHONPATH=. python3 -m src.cli.commands ...`.

## 2. Описать источник

```bash
mkdir -p sources/CRM
cat > sources/CRM/source.json <<'JSON'
{"name": "CRM", "key_label": "customer_id"}
JSON
```

`key_label` — имя столбца с уникальным идентификатором объекта. Подробнее —
[`../reference/config-format.md`](../reference/config-format.md).

## 3. Подготовить данные (колоночный JSON)

`batch_2024-01.json`:

```json
{
  "customer_id": ["101", "102", "103"],
  "email":       ["alice@example.com", "bob@example.com", "carol@example.com"],
  "phone":       ["+7-900-000-0001", "+7-900-000-0002", null]
}
```

`null` = удаление значения (см. [`../explanation/delete-semantics.md`](../explanation/delete-semantics.md)).

## 4. Загрузить

```bash
ds --db data.db load sources/CRM batch_2024-01.json --dt 1704067200
# loaded 6 transaction(s)
```

`--dt` — бизнес-время «с какого момента данные актуальны» (Unix-timestamp), не время запуска.

Второй батч позже по времени:

`batch_2024-02.json`:

```json
{ "customer_id": ["102", "104"], "email": ["bob.new@example.com", "dave@example.com"] }
```

```bash
ds --db data.db load sources/CRM batch_2024-02.json --dt 1706745600
# loaded 2 transaction(s)
```

`customer_id=102` уже был → `POST` (перезапись); `104` впервые → `PATCH`. Тип операции
`ds` выбирает сам (см. [`../explanation/act-semantics.md`](../explanation/act-semantics.md)).

## 5. Посмотреть, что получилось

Команды `ds get` сейчас нет — читаем журнал напрямую:

```bash
sqlite3 data.db "
SELECT t.cnt, a.name AS act, datetime(t.dt,'unixepoch') AS dt,
       s.name AS src, l.name AS lb, i.value AS id, v.value AS val
FROM transactions t
JOIN acts a ON a.act_id=t.act
JOIN srcs s ON s.src_id=t.src
JOIN lbs  l ON l.lb_id =t.lb
JOIN ids  i ON i.id_id =t.id
LEFT JOIN vals v ON v.val_id=t.val
ORDER BY t.cnt;"
```

Больше запросов — [`reading-state-via-sql.md`](reading-state-via-sql.md).

## Дальше

- Как это работает внутри → [`loading-data.md`](loading-data.md), раздел 2.
- Модель данных → [`../explanation/data-model.md`](../explanation/data-model.md).
- Запускаемые примеры (можно взять за основу тестов) → [`../../examples/`](../../examples/).
