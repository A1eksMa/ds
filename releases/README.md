# Changelog

Архивы в этой папке — рабочая версия кода (без тестов), готовая к распаковке и запуску.
Имя архива содержит номер версии: `ds-<version>.tar.gz`.

## Распаковка

```bash
mkdir -p /path/to/target/folder
tar -xzf ds-<version>.tar.gz -C /path/to/target/folder
```

Например:

```bash
mkdir -p ./ds-0.2.0a1
tar -xzf ds-0.2.0a1.tar.gz -C ./ds-0.2.0a1
```

---

## 0.6.0a1 — `ds-0.6.0a1.tar.gz`

Возврат пути чтения (`ds get`) поверх текущей схемы + полная переработка документации.
Схема БД не менялась.

- **Документация переразбита** (Diátaxis): `docs/{explanation,reference,guides,decisions,roadmap,attic}/`.
  `reference/` выверен по коду; аспирационный `docs/proposals/` и корневые `CONFIG_FORMAT.md` /
  `TODO.md` перенесены в `docs/attic/` с пометкой «не соответствует коду». Добавлены ADR
  (`docs/decisions/`), дорожная карта ядра (`docs/roadmap/`), запускаемые примеры
  (`examples/` + `tests/examples/`). Корневой `README.md` переписан, добавлен `CONTRIBUTING.md`.
  Удалён устаревший фикстур `sources/object/`.
- Новая CLI-команда `ds get` — свёртка журнала в состояние источника (Level 1) и выгрузка в
  JSON. Реализация — `src/service/get.py` (`fold_source` / `build_source` / `run_get` /
  `load_preset`). Это переписанный заново путь чтения (был в 0.3.0a1–0.4.0a1 как
  `fold_state`/`build_state`/`build_export`, снят в 0.5.0a1).
  - Параметры: `--src` (повторяемый), `--lb` (повторяемый), `--dt` (срез / машина времени),
    `--archive`, `--preset FILE` (секция `query`), `--out DIR` (по файлу `<Source>.json` на
    источник; без `--out` — stdout). Явные флаги перекрывают пресет.
  - Свёртка — по `(dt, cnt)` (ADR-0006), а не по `cnt`.
  - Формат выхода: `{meta, data}` на источник, широкая таблица (строка на `id`); `null` =
    последняя операция `DELETE`, отсутствие ключа = транзакции не было. `meta.gen_max_cnt` —
    водяной знак для детекта устаревания на стороне потребителя.
  - Схема БД **не менялась**. Манифест и `.js`-обёртка под `file://` — задача потребителя,
    не ядра (см. `docs/reference/get-output-format.md`).
- Тесты: `tests/service/test_get.py` (21), get-часть `tests/cli/test_commands.py` (5),
  `examples/04-get/`. Итого 210, все проходят.
- Документация: `docs/reference/get-output-format.md` (новый контракт), `docs/reference/cli.md`,
  `docs/explanation/single-source-fold.md`; старый `docs/roadmap/state-retrieval.md` (спека
  0.4.0a1) → `docs/attic/get-0.4.0a1.md`.

## 0.5.0a1 — `ds-0.5.0a1.tar.gz`

Откат к ядру: три папки уровня Level 1 (`loader/`, `processing/`, `api/`) объединены в один
пакет `src/service/`, и в схему БД внесены две правки из `TODO.md`, накопившиеся до того, как
Level 1 продвинулся дальше.

- `src/loader/`, `src/processing/`, `src/api/` удалены целиком — вместе с ними ушли
  `fold_state()`/`build_state()` (Processing Engine Level 1) и `build_export()`/
  `export_state_file()` (Core API), а с ними и CLI-команда `ds get` из 0.4.0a1. Они основаны на
  старой схеме (`cnt`-only коллизии, метки без привязки к источнику) и будут переписаны заново
  поверх новой схемы — решили не патчить дважды.
- Новый `src/service/`: `load.py` (объединяет прежние `loader/json_loader.py` и
  `api/service.py::load`/`load_file`) и `validate.py` (перенесён без изменений). CLI
  (`src/cli/commands.py`) сохраняет только команду `load` — это рабочий прообраз новой структуры,
  один модуль на функцию вместо трёх параллельных папок.
- `TODO.md` #2: `Transaction`/`transactions` получили поле `created_at` — технический timestamp
  физической вставки записи, отдельно от бизнесового `dt`. Генерируется один раз на стороне
  Python через `ClockPort` (не читается обратно из БД через `julianday('now')`).
- `TODO.md` #4: `Lb` теперь специфична для источника — `lbs` уникальна по `(src_id, name)`, а не
  только по `name`. `Src.key_label` стал nullable, чтобы разорвать цикл создания `Src`↔`Lb`:
  источник создаётся первым с пустым `key_label`, затем интернируется его ключевая метка (уже с
  `src_id`), затем `key_label` дозаписывается новым методом `StoragePort.src_set_key_label()`.
- `TODO.md` #3 (сортировка `fold_state` по `(dt, cnt)`) сознательно отложена вместе с остальным
  Level 1 — сейчас его просто нет в коде, переделывать нечего.
- `docs/loader.md` обновлён под новую схему и структуру модулей; `docs/get.md` устарел
  (описывает удалённую команду) и будет пересмотрен отдельно.
- Тесты: 180 (без учёта удалённых `tests/loader/`, `tests/processing/`, `tests/api/` и
  get-тестов из `tests/cli/test_commands.py`), все проходят через `run_tests.sh`.

## 0.4.0a1 — `ds-0.4.0a1.tar.gz`

- Новая CLI-команда `ds get <out.json> [--src NAME] [--lb NAME] [--dt TS] [--archive]` —
  выгрузка состояния (построенного через `build_state()` из 0.3.0a1) в JSON-файл. До этой версии
  `build_state()` не был доступен ни из CLI, ни из API — теперь есть путь чтения, а не только
  записи (`load`).
- `src/api/service.py`: `build_export()` — собирает `{metadata, data}` (формат "внутреннего
  снэпшота" по `docs/proposals/DATABASE_DESIGN.md`, без `configs` из "формата выгрузки"),
  резолвя числовые `src`/`lb`/`id`/`val` из `build_state()` обратно в читаемые
  строки/значения; `export_state_file()` — пишет результат на диск. Фильтры `--src`/`--lb`
  резолвятся по имени через `src_list()`/`lb_list()` без побочных эффектов — неизвестное имя
  возвращает `NotFound`, а не создаёт новую запись.
- Фильтра по конкретному `--id` нет (сознательно) — нет read-only способа найти `id_id` по
  значению, не создавая его.
- `docs/get.md` — подробная документация по `ds get`, по аналогии с `docs/loader.md`; сам
  `docs/loader.md` обновлён (убрано устаревшее "нет команды экспорта/чтения").
- Тесты: 15 новых (`tests/api/test_service.py`, `tests/cli/test_commands.py`), итого 206.

## 0.3.0a1 — `ds-0.3.0a1.tar.gz`

- Начало Processing Engine (Level 1, single source): сборка snapshot-состояния по журналу транзакций.
- `src/processing/single_source.py::fold_state()` — разрешение коллизий в рамках одного источника: сворачивает список транзакций в последнее значение по каждому ключу `(src, lb, id)`, победитель определяется по `cnt` (порядок вставки в хранилище), а не по `dt`. `DELETE` (`val == ValId(0)`) остаётся в state как отдельная запись, а не удаляется из словаря.
- `src/processing/engine.py::build_state()` — собирает state, читая из `StoragePort.txn_query()` с фильтрами по `src_id`/`lb_id`/`id_id`, срезом по времени (`until_dt`, "машина времени") и опциональным включением архива.
- Кросс-источниковое разрешение коллизий по весам доверия (Level 2 / Multi Source) в этой версии не реализовано — каждый `(src, lb, id)` держит своё значение независимо от других источников.
- Тесты: `tests/processing/test_single_source.py`, `tests/processing/test_engine.py`.

## 0.2.0a1 — `ds-0.2.0a1.tar.gz`

- Автоопределение типа операции (`act`) при загрузке данных вместо ручного флага `--act`:
  - значение `null` → `DELETE`
  - записи для `(source, label, id)` раньше не было, либо последняя запись была удалением → `PATCH`
  - для записи уже есть значение → `POST`
- Флаг `--act` убран из CLI (`ds load`) — теперь это не нужно указывать вручную.
- `StoragePort` расширен батчевым методом `txn_last_values()` — предзагружает последнее известное состояние по всем `(label, id)` пар одним запросом на весь батч (учитывает и архив), вместо запроса на каждую вставляемую запись.
- Реализовано в обоих адаптерах (`SQLiteAdapter`, `InMemoryAdapter`) + тесты.

## 0.1.0a1 — `ds-0.1.0a1.tar.gz`

- Первая альфа-версия: перенос инженерного ядра из ветки `dev-core` репозитория `data_sources`.
- Реализовано: доменные типы (`Src`, `Lb`, `Transaction`), `Result`-обёртки (`Ok`/`Err`), `StoragePort` и его реализации (`SQLiteAdapter`, `InMemoryAdapter`), загрузка колоночного JSON (`Data Loader`), CLI-команда `load`.
- Схема БД: `transactions` / `transactions_archive` (event sourcing, партиционирование), string pools (`srcs`, `lbs`, `ids`, `vals`, `acts`).
- Тип операции (`act`) при загрузке задавался вручную через `--act` (post/patch/delete), одинаково для всего файла.
- Не реализовано: Processing Engine (сборка state/снэпшотов, разрешение коллизий по весам доверия, "машина времени"), String Pool Manager как отдельный компонент, многоуровневая семантическая модель (Entity Manager, mapping) — описанные в `docs/proposals/`, но не входящие в эту версию.
