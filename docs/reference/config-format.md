# Формат конфигурации источника (`source.json`)

Как в коде на 0.5.0a1 (`src/config/loader.py`, `src/config/models.py`, `src/config/validator.py`).
Исходно этот файл был заплаткой к `PROJECT_STRUCTURE.md` (там предполагался YAML — реализация
использует JSON, потому что `PyYAML` — внешняя зависимость; см.
[`../explanation/constraints.md`](../explanation/constraints.md)).

## Расположение

Источник описывается папкой с обязательным файлом `source.json`. Путь к этой папке —
позиционный аргумент `ds load <source_dir> ...`. Жёсткой раскладки `data/` в коде нет:
папку источника кладёшь куда удобно, БД задаётся через `--db` (по умолчанию `data.db`).

```
sources/
└── CRM/
    ├── source.json          обязателен
    └── labels/              опционально; загрузчиком ЧИТАЕТСЯ, но результат НЕ применяется (см. ниже)
        └── email/
            └── config.json
```

## `source.json`

Обязательные поля: `name`, `key_label`.

```json
{
  "name": "CRM",
  "key_label": "customer_id",
  "p": 0.9,
  "description": "CRM-система"
}
```

| Поле | Тип | Обяз. | По умолч. | Что делает на практике |
|---|---|---|---|---|
| `name` | string | да | — | имя источника; под ним он создаётся в `srcs` |
| `key_label` | string | да | — | имя столбца во входных данных с уникальным `id` объекта |
| `p` | float | нет | `0.5` | **парсится и проверяется на диапазон `[0.0, 1.0]`, но до БД не доходит** — `load` не передаёт его в `src_get_or_create`. Реальный вес источника останется `0.5`. См. [`../explanation/trust-weights.md`](../explanation/trust-weights.md). |
| `description` | string | нет | `null` | парсится, загрузчиком никуда не используется |

## `labels/<name>/config.json`

```json
{ "name": "email", "p": 0.8, "description": "Email адрес клиента" }
```

| Поле | Тип | Обяз. | По умолч. |
|---|---|---|---|
| `name` | string | да | — |
| `p` | float | нет | `0.5` |
| `description` | string | нет | `null` |

**Текущее поведение (0.5.0a1):** `load_source()` читает `labels/*/config.json` и складывает в
`SourceConfig.labels`, но путь загрузки данных (`service/load.py`) этим словарём **не
пользуется** — метки регистрируются на лету при первой загрузке с `p = 0.5`. То есть создавать
`labels/` сейчас смысла нет.

> ⚠️ Несогласованность в коде: `config/validator.py :: validate_source` требует, чтобы
> `key_label` присутствовал в `cfg.labels`, но `service/load.py` `validate_source` **не
> вызывает** (зовёт только `validate_table` по данным). Поэтому на практике `labels/`
> отсутствовать может. Разрыв отмечен как есть, не как желаемое.

## Минимальная рабочая конфигурация

```
sources/CRM/source.json  →  {"name": "CRM", "key_label": "customer_id"}
```

```bash
ds --db data.db load sources/CRM batch_2024-01.json --dt 1704067200
```

Формат самого файла данных — [`data-format.md`](data-format.md). Разбор загрузки —
[`../guides/loading-data.md`](../guides/loading-data.md).
