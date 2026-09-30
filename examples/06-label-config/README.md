# 06 — Инвентарь показателей в `source.json`

`source.json` может декларировать показатели источника заранее — имя, `type` (справочно, для
`ds-loader`/`ds-webui`, само ядро его не проверяет и не парсит данные под него) и два флага:
`archive` и `publish`. Из всей тройки только `archive` на что-то влияет **внутри `ds`**:
показатель с `"archive": true` при `ds load` пишется сразу в `transactions_archive`, минуя
активную таблицу — без отдельного `ds archive`/`ds delete`. `publish` пока только парсится и
хранится — его должен будет читать `ds-loader` при перестроении витрины (ещё не сделано на его
стороне); по умолчанию `false` — публикация это ручной allow-list (`email`/`revenue` явно
включены ниже), а не «всё, кроме исключённого». Подробности —
[`../../docs/reference/config-format.md`](../../docs/reference/config-format.md).

Показатель, не попавший в `labels`, продолжает подхватываться по факту наличия в файле данных
(как и раньше) — декларация обогащает схему, а не ограничивает её.

## Запуск

```bash
bash run.sh /tmp/ex06
```

```
--- ds get: internal_note НЕ в активной выборке (ушло сразу в архив при load) ---
{ ..., "labels": ["email", "internal_note", "revenue"], "data": [{"customer_id": "1", "email": "a@x.com", "revenue": "100"}, ...] }

--- ds get --archive: internal_note виден при явном запросе архива ---
{ ..., "data": [{"customer_id": "1", "email": "a@x.com", "internal_note": "flagged for review", "revenue": "100"}, ...] }
```
