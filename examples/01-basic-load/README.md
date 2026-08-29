# 01 — Базовая загрузка

Два батча в источник `CRM` (`key_label = customer_id`).

- `batch_2024-01.json` (`--dt 1704067200`, 2024-01-01): 3 клиента, `email` + `phone`;
  `phone` клиента 103 — `null`.
- `batch_2024-02.json` (`--dt 1706745600`, 2024-02-01): у 102 меняется `email`, добавляется
  клиент 104.

## Запуск

```bash
bash run.sh /tmp/ex01
```

```
loaded 6 transaction(s)
loaded 2 transaction(s)
```

## Что в журнале ([`expected/journal.txt`](expected/journal.txt))

8 транзакций. Из первого батча — 5 `PATCH` (первое появление) + 1 `DELETE` (`phone` 103 =
`null`). Из второго — `POST` для `email` 102 (значение уже было) и `PATCH` для 104 (новый).

Разбор по шагам — [`../../docs/guides/loading-data.md`](../../docs/guides/loading-data.md).
