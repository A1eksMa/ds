# Схема базы данных (как в коде)

> **Контракт / стабильно.** Эта схема — интерфейс, на который завязывается вышестоящий слой.
> Изменения — только через changelog (`releases/README.md`); отдельного номера версии схемы
> нет, привязка идёт к тегу `ds` (см. [`../decisions/0008-no-separate-schema-versioning.md`](../decisions/0008-no-separate-schema-versioning.md)).

Источник истины — строка `_SCHEMA` в `src/adapters/sqlite_adapter.py`. Ниже — она же
дословно. Проектный документ [`../attic/database-design-2025-11.md`](../attic/database-design-2025-11.md)
местами описывает другое (таблицу `state`, чекпоинты, `ORDER BY` во вью) — **в коде этого нет**.

## DDL

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS acts (
    act_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS srcs (
    src_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    UNIQUE NOT NULL,
    description TEXT,
    p           REAL    NOT NULL DEFAULT 0.5,
    key_label   INTEGER,                        -- NULL до бутстрапа (src_set_key_label)
    FOREIGN KEY (key_label) REFERENCES lbs(lb_id)
);

CREATE TABLE IF NOT EXISTS lbs (
    lb_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT,
    p           REAL    NOT NULL DEFAULT 0.5,
    src_id      INTEGER NOT NULL,                -- метки специфичны для источника
    UNIQUE (src_id, name),
    FOREIGN KEY (src_id) REFERENCES srcs(src_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ids (
    id_id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS vals (
    val_id INTEGER PRIMARY KEY AUTOINCREMENT,
    value  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS cnts (
    cnt_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    cnt INTEGER PRIMARY KEY,
    act INTEGER NOT NULL,
    dt  REAL    NOT NULL,
    src INTEGER NOT NULL,
    lb  INTEGER NOT NULL,
    id  INTEGER NOT NULL,
    val INTEGER,
    p   REAL    NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,          -- физическая вставка записи (отдельно от dt)
    FOREIGN KEY (cnt) REFERENCES cnts(cnt_id)  ON DELETE RESTRICT,
    FOREIGN KEY (act) REFERENCES acts(act_id)  ON DELETE RESTRICT,
    FOREIGN KEY (src) REFERENCES srcs(src_id)  ON DELETE RESTRICT,
    FOREIGN KEY (lb)  REFERENCES lbs(lb_id)    ON DELETE RESTRICT,
    FOREIGN KEY (id)  REFERENCES ids(id_id)    ON DELETE RESTRICT,
    FOREIGN KEY (val) REFERENCES vals(val_id)  ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS transactions_archive (
    -- структура идентична transactions
    cnt INTEGER PRIMARY KEY,
    act INTEGER NOT NULL,
    dt  REAL    NOT NULL,
    src INTEGER NOT NULL,
    lb  INTEGER NOT NULL,
    id  INTEGER NOT NULL,
    val INTEGER,
    p   REAL    NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,
    FOREIGN KEY (cnt) REFERENCES cnts(cnt_id)  ON DELETE RESTRICT,
    FOREIGN KEY (act) REFERENCES acts(act_id)  ON DELETE RESTRICT,
    FOREIGN KEY (src) REFERENCES srcs(src_id)  ON DELETE RESTRICT,
    FOREIGN KEY (lb)  REFERENCES lbs(lb_id)    ON DELETE RESTRICT,
    FOREIGN KEY (id)  REFERENCES ids(id_id)    ON DELETE RESTRICT,
    FOREIGN KEY (val) REFERENCES vals(val_id)  ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_txn_dt         ON transactions(dt);
CREATE INDEX IF NOT EXISTS idx_txn_src_lb_id  ON transactions(src, lb, id);
CREATE INDEX IF NOT EXISTS idx_arch_dt        ON transactions_archive(dt);
CREATE INDEX IF NOT EXISTS idx_arch_src_lb_id ON transactions_archive(src, lb, id);

CREATE VIEW IF NOT EXISTS transactions_full AS
    SELECT * FROM transactions
    UNION ALL
    SELECT * FROM transactions_archive;
```

## PRAGMA при подключении

`SQLiteAdapter.__init__` дополнительно ставит: `journal_mode = WAL`, `synchronous = NORMAL`,
`isolation_level = None` (автокоммит; транзакции управляются явно через `begin/commit/rollback`).

## Справочные таблицы (string pools)

| Таблица | Роль | Уникальность |
|---|---|---|
| `acts` | коды операций: `POST` / `GET` / `PATCH` / `DELETE` | `name` |
| `srcs` | источники + метаданные (`p`, `description`, `key_label`) | `name` |
| `lbs` | показатели + метаданные, **специфичны для источника** | `(src_id, name)` |
| `ids` | значения идентификаторов объектов | `value` |
| `vals` | значения показателей | `value` |
| `cnts` | генератор `cnt` + `created_at` | `cnt_id` |

`val_id` нумеруется с 1; `val = 0` в домене (`ValId(0)`) ↔ `transactions.val IS NULL` — маркер
`DELETE` (см. [`../explanation/delete-semantics.md`](../explanation/delete-semantics.md)).

## Журнал

| Поле | Тип | Смысл |
|---|---|---|
| `cnt` | INTEGER PK | порядковый номер (= `cnts.cnt_id`), глобально уникален, монотонен |
| `act` | → `acts` | тип операции |
| `dt` | REAL | бизнес-время (Unix, секунды с дробной частью), задаётся извне |
| `src` `lb` `id` | → пулы | четвёрка `source–label–id` |
| `val` | → `vals`, nullable | значение; `NULL` = `DELETE` |
| `p` | REAL, `1.0` | вес доверия записи (`p_record`); при загрузке всегда `1.0` |
| `created_at` | REAL | физическое время вставки (генерируется через `ClockPort` на стороне Python) |

Три оси времени (`dt` / `created_at` / `cnt`) — [`../explanation/time-model.md`](../explanation/time-model.md).

## Партиционирование и архив

- `transactions` — активные данные; `transactions_archive` — архив, структура идентична.
- Записи перемещаются между таблицами **без изменения `cnt`** (для того `cnt` и вынесен в
  отдельный пул `cnts` — уникальность сохраняется при переносе).
- `transactions_full` — вью `UNION ALL` обеих таблиц для сквозного ретроспективного чтения.
  **Без `ORDER BY`** — сортировку задаёт запрос.

## Внешние ключи

Все FK — `ON DELETE RESTRICT`: защита от случайного удаления связанных данных. Любое удаление
записи пула требует явного порядка (сначала ссылающиеся транзакции). Это влияет на операции
жизненного цикла и управления сущностями — см.
[`../roadmap/entity-curation.md`](../roadmap/entity-curation.md).

## Чего в схеме нет

- **Таблицы `state`** — свёрнутое состояние нигде не персистится, каждый запрос считает его
  заново (в 0.5.0a1 путь чтения вообще снят). См.
  [`../explanation/single-source-fold.md`](../explanation/single-source-fold.md),
  [`../roadmap/state-retrieval.md`](../roadmap/state-retrieval.md).
- **Чекпоинтов / снэпшотов**, `config.yaml`, таблиц под семантический маппинг.
