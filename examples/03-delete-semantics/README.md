# 03 — Семантика удаления

Жизненный цикл одного значения: задано → удалено → задано снова.

- `step1-create.json` (`--dt 1704067200`): `email` + `phone` для клиента 101 → 2 × `PATCH`.
- `step2-delete-phone.json` (`--dt 1705276800`): `phone` = `null` → `DELETE`.
- `step3-phone-again.json` (`--dt 1706745600`): `phone` снова задан → `PATCH`
  (повторное появление после удаления, **не** `POST`).

## Запуск

```bash
bash run.sh /tmp/ex03
```

```
loaded 2 transaction(s)
loaded 1 transaction(s)
loaded 1 transaction(s)
```

## Журнал ([`expected/journal.txt`](expected/journal.txt))

```
cnt | act    | ... | lb    | id  | val
1   | PATCH  | ... | email | 101 | alice@example.com
2   | PATCH  | ... | phone | 101 | +7-900-000-0001
3   | DELETE | ... | phone | 101 | <null>
4   | PATCH  | ... | phone | 101 | +7-900-000-9999
```

`DELETE` — это запись в журнале (`val IS NULL`), а не стирание истории. После неё следующее
непустое значение — `PATCH`. Подробнее —
[`../../docs/explanation/delete-semantics.md`](../../docs/explanation/delete-semantics.md).
