# Чтение состояния вручную через SQL

> Обычный способ получить состояние источника — **`ds get`** (см.
> [`../reference/cli.md`](../reference/cli.md), [`../reference/get-output-format.md`](../reference/get-output-format.md)).
> Этот документ — про *нижний уровень*: как посмотреть журнал и свернуть значение руками
> через `sqlite3`, когда нужно разобраться в истории объекта или проверить, что делает `get`.

БД — обычный файл SQLite: `sqlite3 data.db`.

Все запросы ниже — поверх сквозного примера из [`loading-data.md`](loading-data.md)
(источник `CRM`, два батча, 8 транзакций).

## Человекочитаемый журнал целиком

Сырые `transactions` содержат только числовые ссылки — нужен `JOIN` со справочниками:

```sql
SELECT
  t.cnt,
  a.name AS act,
  datetime(t.dt, 'unixepoch') AS dt,
  s.name AS source,
  l.name AS label,
  i.value AS id,
  v.value AS value
FROM transactions t
JOIN acts a ON a.act_id = t.act
JOIN srcs s ON s.src_id = t.src
JOIN lbs  l ON l.lb_id  = t.lb
JOIN ids  i ON i.id_id  = t.id
LEFT JOIN vals v ON v.val_id = t.val
ORDER BY t.cnt;
```

```
cnt  act     dt                   source  label  id   value
1    PATCH   2024-01-01 00:00:00  CRM     email  101  alice@example.com
2    PATCH   2024-01-01 00:00:00  CRM     phone  101  +7-900-000-0001
3    PATCH   2024-01-01 00:00:00  CRM     email  102  bob@example.com
4    PATCH   2024-01-01 00:00:00  CRM     phone  102  +7-900-000-0002
5    PATCH   2024-01-01 00:00:00  CRM     email  103  carol@example.com
6    DELETE  2024-01-01 00:00:00  CRM     phone  103
7    POST    2024-02-01 00:00:00  CRM     email  102  bob.new@example.com
8    PATCH   2024-02-01 00:00:00  CRM     email  104  dave@example.com
```

## Текущее значение одного показателя («последняя запись побеждает»)

```sql
SELECT v.value
FROM transactions t
LEFT JOIN vals v ON v.val_id = t.val
WHERE t.src = (SELECT src_id FROM srcs WHERE name='CRM')
  AND t.lb  = (SELECT lb_id  FROM lbs  WHERE name='email'
               AND src_id = (SELECT src_id FROM srcs WHERE name='CRM'))
  AND t.id  = (SELECT id_id  FROM ids  WHERE value='102')
ORDER BY t.dt DESC, t.cnt DESC
LIMIT 1;
-- bob.new@example.com
```

> Порядок `ORDER BY t.dt DESC, t.cnt DESC` соответствует целевому правилу свёртки Level 1
> (см. [`../explanation/single-source-fold.md`](../explanation/single-source-fold.md)):
> приоритет по бизнес-времени, при равенстве — по `cnt`. Фильтр по `lbs` включает `src_id`,
> потому что метки специфичны для источника.

## Вся история объекта (виден `DELETE`)

```sql
SELECT t.cnt, a.name AS act, l.name AS label, v.value AS value
FROM transactions t
JOIN acts a ON a.act_id = t.act
JOIN lbs  l ON l.lb_id  = t.lb
LEFT JOIN vals v ON v.val_id = t.val
WHERE t.id = (SELECT id_id FROM ids WHERE value='103')
ORDER BY t.cnt;
```

```
cnt  act     label  value
5    PATCH   email  carol@example.com
6    DELETE  phone
```

## Срез на прошлый момент («машина времени»)

Добавить в `WHERE` условие `t.dt <= :T` (и, если нужен архив, читать из вью
`transactions_full` вместо `transactions`).

## Количество транзакций по источнику

```sql
SELECT s.name, COUNT(*) AS txn_count
FROM transactions t JOIN srcs s ON s.src_id = t.src
GROUP BY s.name;
```

## На что обратить внимание

- **Кросс-источникового разрешения по весам `p` (Level 2) нет** — если один и тот же
  `(label, id)` есть в нескольких источниках, вы увидите несколько строк, по одной на
  источник. Выбор «чьё значение главнее» ядро не делает.
- **Каждый такой запрос считает состояние с нуля** — персистентного снэпшота (таблицы `state`)
  не существует.
- **Метка ищется вместе с `src_id`** — `WHERE name='email'` без источника вернёт все
  одноимённые метки всех источников.
