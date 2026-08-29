# Дорожная карта ядра

Что ещё **сядет в это ядро**, но пока не реализовано. Это не весь первоначальный замысел —
только то, что укладывается в границы ядра-хранилища
([`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)). Аспирационная
архитектура целиком — в [`../attic/`](../attic/), и по ней **не строим**.

Отличие от `attic/`: `roadmap/` — «сделаем здесь»; `attic/` — «замысел, от которого отклонились
или который передан другому слою».

| Тема | Что | Было в коде | Заметки |
|---|---|---|---|
| [state-retrieval](state-retrieval.md) | вернуть `ds get` — состояние источника на момент времени (Level 1) для внешних систем | да, 0.4.0a1 (снято) | внешний интерфейс переносится как есть; свёртка — по `(dt, cnt)` |
| [single-source-fold](single-source-fold.md) | реинстейт `fold_state` / `build_state` | да, 0.3.0a1 (снято) | закрывает только Level 1 |
| [entity-curation](entity-curation.md) | merge / split / delete / rename над `srcs`/`lbs`/`ids`/`vals` | нет | сначала решить [ADR-0009](../decisions/0009-entity-curation-rewrite-vs-events.md) |
| [lifecycle-cli](lifecycle-cli.md) | вывести `txn_archive` / `txn_delete` в CLI | в порту — да, в CLI — нет | |
| [schema-migration](schema-migration.md) | инструменты миграции при изменении схемы ядра | нет | |
| [optimization](optimization.md) | индексы, `VACUUM`, дедупликация, чистка осиротевших записей пулов | базовые индексы — да | |

## Разумный порядок

Из прежнего `TODO.md` и логики зависимостей: сначала стабилизировать схему (возможные
оставшиеся правки) → `single-source-fold` + `state-retrieval` (путь чтения нужен всем) →
`lifecycle-cli` → `entity-curation` (самый большой blast radius, требует ADR-0009) →
`schema-migration` / `optimization` по мере необходимости.

## Не в этом ядре

Семантический маппинг, разрешение коллизий между источниками по `p` (Level 2), управление
приоритетами пользователем, UI, BI — вышестоящий слой (отдельный проект). См.
[`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md).
