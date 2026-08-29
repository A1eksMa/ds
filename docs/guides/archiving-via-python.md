# Архивирование и удаление через Python

> Архивирование (`txn_archive`) и физическое удаление (`txn_delete`) реализованы на уровне
> `StoragePort`, но **в CLI не выведены**. Вывести их в `ds` — задача из
> [`../roadmap/lifecycle-cli.md`](../roadmap/lifecycle-cli.md). Пока — только из кода/REPL.

## Архивирование («мягкое» удаление)

Переносит все транзакции с `dt <= until_dt` из `transactions` в `transactions_archive`.
Данные не теряются, `cnt` не меняется; выборки по умолчанию их больше не видят.

```python
from src.adapters.sqlite_adapter import SQLiteAdapter

db = SQLiteAdapter("data.db")
db.begin()
result = db.txn_archive(until_dt=1704067200)   # Ok(<число перемещённых>)
db.commit()
print(result)
```

После этого обычная выборка (`txn_query(...)`) архив не включает; чтобы прочитать вместе с
архивом — `txn_query(..., include_archive=True)` (читает вью `transactions_full`).

## Физическое удаление («жёсткое»)

Безвозвратно удаляет транзакции источника (опционально — только одной метки).

```python
db.begin()
result = db.txn_delete(src_id=1)                # все транзакции источника 1
# или: db.txn_delete(src_id=1, lb_id=3)         # только метка 3 этого источника
db.commit()
print(result)                                   # Ok(<число удалённых>)
```

> FK во всех таблицах — `ON DELETE RESTRICT`. Удаление записей самих пулов (`srcs`, `lbs`,
> `ids`, `vals`) требует, чтобы на них не осталось ссылок из журнала — то есть сначала
> удаляются/переносятся транзакции. Инструментов для чистки осиротевших записей пулов пока
> нет — [`../roadmap/optimization.md`](../roadmap/optimization.md).

## Зачем это в ядре

Журнал только растёт (append-only, см. [`../explanation/event-sourcing.md`](../explanation/event-sourcing.md)).
Архивирование и удаление — инструменты управления объёмом хранилища и соблюдения политик
хранения данных. Это операции **инженера**, не пользователя, и они остаются в ядре
(см. [`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)).
