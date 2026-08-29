# Формат входных данных: колоночный JSON

## Форма

JSON-объект верхнего уровня. Каждый ключ — имя столбца (показателя), значение — список
значений этого столбца. Все списки одной длины.

```json
{
  "customer_id": ["101",              "102",            "103"],
  "email":       ["alice@example.com", "bob@example.com", "carol@example.com"],
  "phone":       ["+7-900-000-0001",   "+7-900-000-0002", null]
}
```

Строка `i` таблицы — это `i`-е значение из каждого списка.

## Правила (проверяются `service/validate.py :: validate_table`)

| Правило | Нарушение → |
|---|---|
| Верхний уровень — объект (`dict`) | `ValidationError(field="data")` |
| Значение каждого ключа — список | `ValidationError(field=<col>)` |
| Столбец `key_label` (из `source.json`) присутствует | `ValidationError(field=<key_label>)` |
| Все столбцы одной длины | `ValidationError(field="columns", ...lengths)` |
| В `key_label` нет `null` | `ValidationError(field=<key_label>)` |
| Значения `key_label` уникальны в пределах файла (после приведения к строке) | `ValidationError(field=<key_label>)` |

При любой ошибке валидации загрузка не начинается — в БД ничего не пишется.

## Семантика значений

| Во входных данных | Что происходит |
|---|---|
| строка | интернируется в `vals`, операция `PATCH` или `POST` (см. [`../explanation/act-semantics.md`](../explanation/act-semantics.md)) |
| число (`int` / `float`) | приводится к строке (`str(raw)`), дальше как строка |
| `null` | операция `DELETE`, `val = 0` (см. [`../explanation/delete-semantics.md`](../explanation/delete-semantics.md)) |

## Что необязательно

- **Не все столбцы обязаны быть в каждом файле** — можно грузить только часть показателей
  (частичные загрузки работают).
- Порядок ключей в JSON значения не имеет.
- Ключевой столбец (`key_label`) сам транзакций не создаёт — только даёт `id` для остальных
  ячеек строки.

## Кодировка

Файл читается как UTF-8 (`path.read_text(encoding="utf-8")`). Некорректный JSON или
ошибка чтения → `Err(StorageError(...))`, файл на диске не трогается.
