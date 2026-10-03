# Дорожная карта ядра

Что ещё **сядет в это ядро**, но пока не реализовано. Это не весь первоначальный замысел —
только то, что укладывается в границы ядра-хранилища
([`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)). Аспирационная
архитектура целиком — в [`../attic/`](../attic/), и по ней **не строим**.

Отличие от `attic/`: `roadmap/` — «сделаем здесь»; `attic/` — «замысел, от которого отклонились
или который передан другому слою».

| Тема | Что | Было в коде | Заметки |
|---|---|---|---|
| [entity-curation](entity-curation.md) | merge / split / delete / rename над `srcs`/`lbs`/`ids`/`vals` | rename/merge `lbs` (`ds mv`) — да; остальное — нет | [ADR-0009](../decisions/0009-entity-curation-rewrite-vs-events.md) решён для `lbs`, остальное требует отдельного рассмотрения |
| [lifecycle-cli](lifecycle-cli.md) | вывести `txn_archive` / `txn_delete` в CLI, дедупликация, восстановление из архива | `delete`/`archive`/`unarchive`/`compact` — да (общий селектор src/lb/id/where/cnt/даты) | готово |
| [schema-migration](schema-migration.md) | инструменты миграции при изменении схемы ядра | нет | |
| [optimization](optimization.md) | индексы, `VACUUM`, чистка осиротевших записей пулов | базовые индексы — да; дедупликация транзакций переехала в `lifecycle-cli` (`ds compact`); инкрементальная свёртка (`ds get --cache`) — да | [ADR-0010](../decisions/0010-incremental-fold-cache.md) |

Сделано: выдача состояния (`ds get`, Level 1 свёртка, инкрементальный кэш `--cache`), жёсткое
удаление, архивирование, восстановление из архива и дедупликация (`ds delete`/`ds archive`/
`ds unarchive`/`ds compact`, общий селектор), переименование/слияние показателя и перенос его
истории между источниками (`ds mv`) — см. [`../reference/cli.md`](../reference/cli.md),
[`../reference/get-output-format.md`](../reference/get-output-format.md).

## Разумный порядок

Из прежнего `TODO.md` и логики зависимостей: `lifecycle-cli` → `entity-curation` (самый
большой blast radius для того, что в нём осталось — `srcs`/`ids`/`vals`, split) →
`schema-migration` / `optimization` по мере необходимости. Путь чтения (`ds get`) уже есть.

## Не в этом ядре

Семантический маппинг, разрешение коллизий между источниками по `p` (Level 2), управление
приоритетами пользователем, UI, BI — вышестоящий слой (отдельный проект). См.
[`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md).
