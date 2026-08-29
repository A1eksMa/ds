# Ошибки и коды возврата (как в коде)

## Модель

Операции не бросают исключения для ожидаемых сбоев — возвращают `Err[...]` (см.
[`domain-model.md`](domain-model.md)). Типы ошибок: `NotFound`, `AlreadyExists`,
`ValidationError`, `StorageError`, `IntegrityError`.

## Как CLI превращает ошибку в текст

`src/cli/commands.py :: _err_msg`:

```python
if isinstance(error, NotFound):
    return f"{error.entity} not found: {error.key}"
return error.message          # для всех остальных типов — поле .message
```

`ValidationError` печатается по `.message` (поле `.field` в текст CLI сейчас не попадает).

Выводится как `error: <текст>` в **stderr**, код возврата — `1`.

## Где какие ошибки возникают

| Источник | Тип | Пример |
|---|---|---|
| `config/loader.py` | `StorageError` | нет `source.json`, битый JSON, `missing required field: 'key_label'` |
| `config/validator.py` | `ValidationError` | `p` вне `[0.0, 1.0]`; `key_label` не найден среди `labels` |
| `service/validate.py` | `ValidationError` | столбцы разной длины; `null`/дубли в `key_label`; `key_label` отсутствует в данных |
| `service/load.py` | `StorageError` | не читается файл данных, ошибка `json.loads` |
| адаптер хранилища | `StorageError` / `IntegrityError` | ошибка SQLite, нарушение FK/`UNIQUE` |

При ошибке в процессе загрузки вызывается `storage.rollback()` — частично записанный батч не
остаётся.

## Коды возврата CLI

| Код | Когда |
|---|---|
| `0` | успех |
| `1` | любая `Err` из конфига / валидации / загрузки |
| `2` | `argparse` не разобрал аргументы (нет подкоманды, неизвестный флаг) |

## Замечание про файлы-результаты

`ds get --out DIR` пишет `<Source>.json` на источник. При ошибке до записи файлы не
создаются (весь документ сначала собирается в памяти). См.
[`get-output-format.md`](get-output-format.md), [`cli.md`](cli.md).
