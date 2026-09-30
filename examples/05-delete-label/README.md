# 05 — Жёсткое удаление показателя

`ds delete` физически убирает транзакции из журнала — навсегда, из **обеих** таблиц
(`transactions` и `transactions_archive`; см. [`../../docs/roadmap/lifecycle-cli.md`](../../docs/roadmap/lifecycle-cli.md)).
Это не то же самое, что `DELETE`-акт (`val: null`, см. [`03-delete-semantics`](../03-delete-semantics/)) —
там запись остаётся в журнале как отметка «значение удалено», её видно в `ds get --archive`
и она разворачивается при машине времени. `ds delete` стирает историю совсем.

Сценарий: загрузили `CRM` с показателем `junk_field`, который оказался не нужен —
удаляем его навсегда, оставляя `email`.

## Запуск

```bash
bash run.sh /tmp/ex05
```

```
--- ds get: junk_field ещё на месте ---
{ ..., "labels": ["email", "junk_field"], "data": [{"customer_id": "1", "email": "a@x.com", "junk_field": "tmp1"}, ...] }

--- ds delete --src CRM --lb junk_field --yes ---
deleted 2 transaction(s)

--- ds get: junk_field пропал из данных (метка в пуле осталась, но пуста) ---
{ ..., "labels": ["email", "junk_field"], "data": [{"customer_id": "1", "email": "a@x.com"}, ...] }
```

`junk_field` остаётся в списке `labels` (это метаданные показателя в пуле `lbs` — их
`ds delete` не трогает, только транзакции), но у него больше нет ни одной транзакции,
поэтому в `data` он не появляется ни у одной строки. Без `--yes` команда спросила бы
подтверждение (`Delete N transaction(s) for CRM.junk_field (active + archived)? [y/N]`) —
непустой ответ, отличный от `y`/`yes`, или недоступный stdin отменяют операцию (код возврата
`1`, `aborted` в stderr).
