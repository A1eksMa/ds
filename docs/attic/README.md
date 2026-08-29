# Архив: первоначальный замысел

Файлы в этой папке — проектные документы ноября 2025 года, написанные **до** реализации.
Они описывают гораздо более крупную систему, чем та, что построена и поддерживается сейчас:
11 компонентов, двухуровневый движок обработки, Entity Manager, семантический маппинг,
таблица `state` и чекпоинты, YAML-конфигурация.

**Кодовая база по этим документам не строится.** Проект намеренно заморожен на слое
ядра-хранилища (см. [`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md)).
Обработка, разрешение коллизий между источниками и UI — задача отдельного, ещё не начатого
проекта верхнего слоя.

Документы сохранены:
- как источник идей и требований для будущего слоя обработки;
- как история проектных решений (часть из них перенесена в [`../decisions/`](../decisions/));
- чтобы было видно, от чего и почему отклонилась реализация.

| Файл | Что это было | Где актуальное |
|---|---|---|
| `framework-vision-2025-11.md` | общее описание фреймворка (черновик с плейсхолдерами) | [`../explanation/overview.md`](../explanation/overview.md), [`../explanation/scope-and-non-goals.md`](../explanation/scope-and-non-goals.md) |
| `components-architecture-2025-11.md` | 11 компонентов, двухуровневая обработка | [`../reference/architecture.md`](../reference/architecture.md) |
| `database-design-2025-11.md` | схема БД + state + снэпшоты | [`../reference/database-schema.md`](../reference/database-schema.md), [`../roadmap/`](../roadmap/) |
| `project-structure-2025-11.md` | раскладка модулей и dev/prod-версий | [`../reference/architecture.md`](../reference/architecture.md), `../../CONTRIBUTING.md` |
| `todo-2025-08.md` | обсуждение 4 доработок (август 2025) | [`../decisions/`](../decisions/) (ADR 0004–0006), [`../roadmap/`](../roadmap/) |
