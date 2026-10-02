# 13 — `mv` перенос показателя в другой источник

Показатель раньше заходил из CRM, а теперь поставляется из ERP — оба источника уже
существуют и уже несут собственные данные.

```bash
ds --db data.db mv --src SRC --lb LB --to-src SRC2 --to-lb LB2 [--yes]
```

`--to-src` здесь отличается от `--src` — вся история показателя (активная и
архивная) физически переносится в указанный источник: на каждой затронутой
транзакции переписываются и `lb`, и `src` (имя показателя при этом можно сохранить
или сменить одновременно, как в [`12-mv-rename`](../12-mv-rename/)). Новых записей
журнала не создаётся — перемещаются существующие.

Если бы ERP ещё не существовал, `ds mv` создал бы его автоматически (так же, как
`ds load` создаёт источник при первой загрузке, см. [`storage-port.md`](../../docs/reference/storage-port.md)) —
здесь это не так: ERP уже содержит собственные данные (`status`), не связанные с
переносимым показателем, и они остаются нетронутыми.

## Запуск

```bash
bash run.sh /tmp/ex13
```

```
--- ds get --src CRM: manufacturer пока в CRM ---
{ ..., "labels": ["manufacturer"], "data": [
  {"customer_id": "101", "manufacturer": "Acme"},
  {"customer_id": "102", "manufacturer": "Globex"}
]}

--- ds mv --src CRM --lb manufacturer --to-src ERP --to-lb manufacturer --yes ---
moved 2 transaction(s): CRM.manufacturer -> ERP.manufacturer (new label)

--- ds get --src CRM: manufacturer больше не существует в CRM ---
{ ..., "labels": [], "data": [] }

--- ds get --src ERP: manufacturer теперь здесь, рядом с уже бывшими данными ---
{ ..., "labels": ["manufacturer", "status"], "data": [
  {"customer_id": "101", "manufacturer": "Acme"},
  {"customer_id": "102", "manufacturer": "Globex"},
  {"customer_id": "201", "status": "shipped"}
]}
```
