# Дорожная карта ядра

Что ещё **сядет в это ядро**, но пока не реализовано. Это не весь первоначальный замысел —
только то, что укладывается в границы ядра-хранилища
([`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)). Аспирационная
архитектура целиком — в [`../attic/`](../attic/), и по ней **не строим**.

Отличие от `attic/`: `roadmap/` — «сделаем здесь»; `attic/` — «замысел, от которого отклонились
или который передан другому слою».

| Тема | Что | Было в коде | Заметки |
|---|---|---|---|
| [entity-curation](entity-curation.md) | merge / split / delete / rename над `srcs`/`lbs`/`ids`/`vals` | нет | сначала решить [ADR-0009](../decisions/0009-entity-curation-rewrite-vs-events.md) |
| [lifecycle-cli](lifecycle-cli.md) | вывести `txn_archive` / `txn_delete` в CLI | `delete` — да; `archive`/`restore` — нет | `archive` ещё и нужно расширить фильтром src/lb в порту |
| [schema-migration](schema-migration.md) | инструменты миграции при изменении схемы ядра | нет | |
| [optimization](optimization.md) | индексы, `VACUUM`, дедупликация, чистка осиротевших записей пулов | базовые индексы — да | |

Сделано: выдача состояния (`ds get`, Level 1 свёртка) и жёсткое удаление (`ds delete`) — см.
[`../reference/cli.md`](../reference/cli.md), [`../reference/get-output-format.md`](../reference/get-output-format.md).

## Разумный порядок

Из прежнего `TODO.md` и логики зависимостей: `lifecycle-cli` → `entity-curation` (самый
большой blast radius, требует ADR-0009) → `schema-migration` / `optimization` по мере
необходимости. Путь чтения (`ds get`) уже есть.

## Не в этом ядре

Семантический маппинг, разрешение коллизий между источниками по `p` (Level 2), управление
приоритетами пользователем, UI, BI — вышестоящий слой (отдельный проект). См.
[`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md).
