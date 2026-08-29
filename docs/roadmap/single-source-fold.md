# [roadmap] Свёртка состояния Level 1 (`fold_state` / `build_state`)

> **Статус: не реализовано.** Было в 0.3.0a1, снято в 0.5.0a1 вместе с Processing Engine.
> Целевая модель — [`../explanation/single-source-fold.md`](../explanation/single-source-fold.md).

## Что нужно

Функции, восстанавливающие состояние по журналу:

- **`build_state(...)`** — собрать список транзакций из `StoragePort.txn_query()` с фильтрами
  `src_id` / `lb_id` / `id_id`, срезом `until_dt` («машина времени») и опциональным
  `include_archive`.
- **`fold_state(txns)`** — свернуть список в словарь `{(src_id, lb_id, id_id): val_id}`,
  победитель по ключу — по правилу Level 1.

Потребитель — `ds get` ([`state-retrieval.md`](state-retrieval.md)) и, в будущем, внешний
слой обработки.

## Правило свёртки (из [ADR-0006](../decisions/0006-fold-order-dt-cnt.md))

Ключ сортировки — **`(dt, cnt)`**, побеждает последний:

1. больший `dt` (бизнес-время);
2. при равном `dt` — больший `cnt`.

**Не** по `cnt` в одиночку (как было в 0.3.0a1) — задержавшаяся запись с более ранним `dt` не
должна затирать более новую.

`DELETE` (`val_id == 0`) остаётся в результате как явная запись, а не выкидывается.

## Что переписать при реализации

- Развернуть тесты, зафиксировавшие старое поведение: `test_fold_state_winner_decided_by_cnt_not_dt`,
  `test_fold_state_later_cnt_overwrites_earlier_for_same_key`,
  `test_fold_state_is_independent_of_input_order`.
- Добавить тест: равный `dt` у двух транзакций одного источника → побеждает больший `cnt`.
- docstring `fold_state` — под правило `(dt, cnt)`.
- Учесть текущую схему: метки специфичны для источника, у транзакций есть `created_at`
  (в свёртке не участвует).

## Граница

Закрывает **только Level 1** (внутри источника). Level 2 (между источниками, по весам `p`) —
вне ядра ([`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)).
