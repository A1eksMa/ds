# 11 — `unarchive` по условию на значение показателя (`--where`)

`ds unarchive` — зеркало `ds archive`: тот же общий селектор «что затронуть»
(`src/service/selector.py`, см. [`07-archive-where`](../07-archive-where/)), но переносит
подходящие **архивные** транзакции обратно в активную таблицу вместо активных в архив.

`--where LB=VALUE` резолвится одинаково для `archive` и `unarchive` — сверткой (Level 1,
активные + архивные транзакции, «на сейчас») показателя `LB`, независимо от того, в какой
таблице сейчас физически лежит запись. Поэтому один и тот же `--where is_test_account=true`
сначала архивирует клиента 102 целиком, а потом тем же условием находит его снова и
возвращает обратно — `cnt` при этом не меняется (`unarchive` не создаёт новых записей
журнала, только перемещает существующие).

## Запуск

```bash
bash run.sh /tmp/ex11
```

```
--- ds archive --where is_test_account=true --yes ---
archived 2 transaction(s)

--- ds get: клиент 102 (test-аккаунт) в архиве, не виден без --archive ---
{ ..., "rows": 2, "data": [{"customer_id": "101", ...}, {"customer_id": "103", ...}] }

--- ds unarchive --where is_test_account=true --yes ---
unarchived 2 transaction(s)

--- ds get: клиент 102 снова активен, как до архивирования ---
{ ..., "rows": 3, "data": [..., {"customer_id": "102", "email": "bob@e.com", "is_test_account": "true"}] }
```
