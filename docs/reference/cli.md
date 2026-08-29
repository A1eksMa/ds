# CLI `ds` (как в коде)

Точка входа — `src/cli/commands.py :: main` (`pyproject.toml` → `[project.scripts] ds`).
Реализована на `argparse`, только stdlib.

> В 0.5.0a1 доступна **одна** подкоманда — `load`. Команда `ds get` (выгрузка состояния) была
> в 0.4.0a1, снята при откате к ядру и будет переписана — [`../roadmap/state-retrieval.md`](../roadmap/state-retrieval.md).

## Общий вид

```
ds [--db PATH] <command> ...
```

| Аргумент | Обязателен | Значение |
|---|---|---|
| `--db PATH` | нет | путь к файлу SQLite. По умолчанию `data.db` в текущей директории. Создаётся автоматически со схемой, если файла нет. |
| `<command>` | да | сейчас только `load` |

## `ds load`

```
ds [--db PATH] load <source_dir> <data_file> [--dt TS]
```

| Аргумент | Обязателен | Значение |
|---|---|---|
| `source_dir` | да | папка с `source.json` (см. [`config-format.md`](config-format.md)) |
| `data_file` | да | путь к файлу колоночного JSON (см. [`data-format.md`](data-format.md)) |
| `--dt TS` | нет | Unix-timestamp «с какого момента данные актуальны» (бизнес-время). По умолчанию — `time.time()` в момент запуска. |

Флага выбора типа операции (`--act`) **нет** — `act` определяется автоматически по ячейке.

### Вывод

- Успех: `loaded <N> transaction(s)` в stdout, код возврата `0`.
- Ошибка: `error: <сообщение>` в stderr, код возврата `1`. Подробнее — [`errors.md`](errors.md).

### Пример

```bash
ds --db data.db load sources/CRM batch_2024-01.json --dt 1704067200
# loaded 6 transaction(s)
```

Полный разбор с реальным выводом и содержимым таблиц — [`../guides/loading-data.md`](../guides/loading-data.md).
Запускаемые примеры — [`../../examples/`](../../examples/).

## Запуск без установки пакета

```bash
PYTHONPATH=. python3 -m src.cli.commands load sources/CRM batch_2024-01.json --dt 1704067200
```

## Коды возврата

| Код | Когда |
|---|---|
| `0` | команда выполнена |
| `1` | ошибка (конфиг, валидация, ввод-вывод, хранилище) — сообщение в stderr |
| `2` | ошибка разбора аргументов (`argparse`) |
