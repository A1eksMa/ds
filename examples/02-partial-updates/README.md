# 02 — `POST` vs `PATCH`

Показывает, что тип операции определяется **по ячейке**, а не по файлу.

- `first.json` (`--dt 1704067200`): `email` для 101 и 102 — оба `PATCH` (первое появление).
- `second.json` (`--dt 1706745600`): `email` для 102 (уже был → `POST`) и 103 (новый → `PATCH`).

## Запуск

```bash
bash run.sh /tmp/ex02
```

```
loaded 2 transaction(s)
loaded 2 transaction(s)
```

## Журнал ([`expected/journal.txt`](expected/journal.txt))

```
cnt | act   | ... | id  | val
1   | PATCH | ... | 101 | alice@example.com
2   | PATCH | ... | 102 | bob@example.com
3   | POST  | ... | 102 | bob.updated@example.com
4   | PATCH | ... | 103 | carol@example.com
```

Один и тот же файл `second.json` дал и `POST`, и `PATCH`. Подробнее —
[`../../docs/explanation/act-semantics.md`](../../docs/explanation/act-semantics.md).
