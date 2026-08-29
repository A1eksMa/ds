> ⚠️ **АРХИВ — первоначальный замысел (ноябрь 2025).**
> Описанная здесь раскладка модулей (`src/storage/`, `src/pools/`, `src/core/`, `src/entities/`,
> YAML-конфиги, `sql/`, `snapshots/`) **не соответствует коду**. Реальная структура —
> `docs/reference/architecture.md`. Политика разделения dev/prod-версий перенесена в
> `CONTRIBUTING.md`.

---

# Структура проекта фреймворка

> Дата: 2025-11-05
> Статус: Финализировано

---

## Полная структура (ветка разработчика)

```
framework/
├── README.md
├── LICENSE
├── setup.py                          # Для установки в dev-режиме
├── requirements-dev.txt               # Только для разработки (если нужно)
│
├── src/                              # Основной код фреймворка
│   ├── __init__.py
│   ├── main.py                       # Точка входа для CLI
│   │
│   ├── cli/                          # CLI компонент
│   │   ├── __init__.py
│   │   ├── parser.py                 # argparse логика
│   │   └── commands.py               # Обработчики команд
│   │
│   ├── core/                         # Core API
│   │   ├── __init__.py
│   │   ├── api.py                    # Основной API класс
│   │   └── orchestrator.py           # Координация компонентов
│   │
│   ├── storage/                      # Storage Engine
│   │   ├── __init__.py
│   │   ├── engine.py                 # Основной класс Storage Engine
│   │   ├── schema.py                 # Создание/миграции схемы БД
│   │   └── transactions.py           # Управление транзакциями
│   │
│   ├── pools/                        # String Pool Manager
│   │   ├── __init__.py
│   │   ├── manager.py                # Основной менеджер pools
│   │   ├── small_pool.py             # Кешируемые pools (srcs, lbs, ids, acts)
│   │   └── large_pool.py             # Простые pools для vals
│   │
│   ├── loader/                       # Data Loader
│   │   ├── __init__.py
│   │   ├── json_loader.py            # Загрузка JSON данных
│   │   └── validator.py              # Валидация входных данных
│   │
│   ├── entities/                     # НОВЫЙ: Entity Manager
│   │   ├── __init__.py
│   │   ├── manager.py                # Управление глобальными сущностями
│   │   ├── mapper.py                 # Маппинг source → entity
│   │   └── validator.py              # Валидация семантической консистентности
│   │
│   ├── processing/                   # Processing Engine (Двухуровневый)
│   │   ├── __init__.py
│   │   ├── engine.py                 # Главный координатор двух уровней
│   │   │
│   │   ├── single_source/            # НОВЫЙ: Уровень 1 - Single Source
│   │   │   ├── __init__.py
│   │   │   ├── processor.py          # Основной процессор одного источника
│   │   │   ├── time_resolver.py      # Разрешение временных коллизий
│   │   │   ├── normalizer.py         # Нормализация и типизация данных
│   │   │   └── rest_operations.py    # REST API операции (POST/GET/PATCH/DELETE)
│   │   │
│   │   ├── multi_source/             # НОВЫЙ: Уровень 2 - Multi Source
│   │   │   ├── __init__.py
│   │   │   ├── integrator.py         # Основной интегратор источников
│   │   │   ├── conflict_resolver.py  # Разрешение коллизий по весам доверия
│   │   │   └── entity_merger.py      # Объединение данных по сущностям
│   │   │
│   │   └── semantic/                 # НОВЫЙ: Семантический маппинг
│   │       ├── __init__.py
│   │       ├── mapper.py             # Маппинг между источниками и сущностями
│   │       └── entity_resolver.py    # Разрешение семантических конфликтов
│   │
│   ├── snapshots/                    # Snapshot Manager (Расширенный)
│   │   ├── __init__.py
│   │   ├── manager.py                # Управление снэпшотами
│   │   ├── builder.py                # Построение снэпшотов
│   │   ├── exporter.py               # Выгрузка в файлы
│   │   └── level_manager.py          # НОВЫЙ: Координация снэпшотов разных уровней
│   │
│   ├── config/                       # Config Manager (Многоуровневый)
│   │   ├── __init__.py
│   │   ├── manager.py                # Координация всех типов конфигураций
│   │   ├── yaml_parser.py            # Парсинг YAML файлов
│   │   ├── entity_config.py          # НОВЫЙ: Работа с конфигами сущностей
│   │   └── mapping_config.py         # НОВЫЙ: Работа с маппингами
│   │
│   ├── archive/                      # Archive Manager (Entity-aware)
│   │   ├── __init__.py
│   │   ├── manager.py                # Управление архивом
│   │   ├── lifecycle.py              # Жизненный цикл данных
│   │   └── entity_aware_archive.py   # НОВЫЙ: Архивирование с учетом entity mappings
│   │
│   └── utils/                        # Общие утилиты (Расширенные)
│       ├── __init__.py
│       ├── logging.py                # Логирование с контекстом уровня обработки
│       ├── exceptions.py             # Исключения для single/multi source обработки
│       ├── helpers.py                # Общие вспомогательные функции
│       ├── semantic_utils.py         # НОВЫЙ: Утилиты для семантического маппинга
│       └── validation_utils.py       # НОВЫЙ: Общие валидаторы
│
├── data/                             # Рабочие данные (конфигурируемое)
│   ├── database.db                   # Основная база данных SQLite
│   │
│   ├── snapshots/                    # Архив снэпшотов (двухуровневые)
│   │   ├── source_level/             # НОВЫЙ: Снэпшоты уровня источников
│   │   │   ├── CRM_state_2025-10-01.json
│   │   │   ├── ERP_state_2025-10-01.json
│   │   │   └── Website_state_2025-10-01.json
│   │   │
│   │   └── integrated/               # НОВЫЙ: Интегрированные снэпшоты
│   │       ├── integrated_state_2025-10-01_v1.json
│   │       ├── integrated_state_2025-10-08_v1.json
│   │       └── integrated_state_2025-10-15_v1.json
│   │
│   └── sources/                      # Многоуровневые конфигурации (конфигурируемое)
│       │
│       ├── entities/                 # НОВЫЙ: Глобальные сущности
│       │   ├── Contract.yaml         # Описание сущности "Договор/Контракт"
│       │   │   # name: "Contract"
│       │   │   # description: "Договор между организацией и клиентом"
│       │   │   # canonical_type: "string"
│       │   │   # aliases: ["Договор", "Контракт", "Agreement"]
│       │   │
│       │   ├── Price.yaml            # Описание разных типов цены
│       │   │   # variants:
│       │   │   #   - PriceWithTax: "Цена с налогами"
│       │   │   #   - PriceWithoutTax: "Цена без налогов"
│       │   │
│       │   ├── Customer.yaml         # Описание клиента
│       │   ├── Product.yaml          # Описание товара
│       │   └── Email.yaml            # Описание email адреса
│       │
│       ├── mappings/                 # НОВЫЙ: Семантические маппинги
│       │   ├── CRM_to_entities.yaml  # Маппинг полей CRM → глобальные сущности
│       │   │   # mappings:
│       │   │   #   labels:
│       │   │   #     "Contract_Number": { entity: "Contract", transformation: "uppercase" }
│       │   │   #     "Final_Price": { entity: "Price.PriceWithTax", transformation: "decimal_2" }
│       │   │
│       │   ├── ERP_to_entities.yaml  # Маппинг полей ERP → глобальные сущности
│       │   │   # mappings:
│       │   │   #   labels:
│       │   │   #     "Agreement_ID": { entity: "Contract", transformation: "uppercase" }
│       │   │   #     "Net_Price": { entity: "Price.PriceWithoutTax", transformation: "decimal_2" }
│       │   │
│       │   ├── Website_to_entities.yaml # Маппинг полей Website → глобальные сущности
│       │   └── global_mappings.yaml  # Глобальные правила маппинга
│       │
│       ├── CRM/                      # Конфигурации источника CRM
│       │   ├── source.yaml           # Описание источника (веса доверия, ключевой label)
│       │   │   # name: "CRM"
│       │   │   # description: "Customer Relationship Management"
│       │   │   # p: 0.9  # вес доверия источника
│       │   │   # key_label: "customer_id"
│       │   │
│       │   └── labels/               # Конфигурации показателей источника
│       │       ├── Email/
│       │       │   └── config.yaml   # data_type: "email", validators, handlers
│       │       ├── Phone/
│       │       │   └── config.yaml   # data_type: "phone", normalization rules
│       │       ├── CustomerID/
│       │       │   └── config.yaml   # data_type: "number", является ключевым полем
│       │       └── Contract_Number/  # Локальное имя (маппится на Entity.Contract)
│       │           └── config.yaml   # data_type: "string", validation patterns
│       │
│       ├── ERP/                      # Конфигурации источника ERP
│       │   ├── source.yaml           # p: 0.95, key_label: "product_id"
│       │   └── labels/
│       │       ├── ProductID/
│       │       │   └── config.yaml   # data_type: "string", ключевое поле
│       │       ├── Price/
│       │       │   └── config.yaml   # data_type: "decimal", precision: 2
│       │       ├── Stock/
│       │       │   └── config.yaml   # data_type: "integer", min_value: 0
│       │       └── Agreement_ID/     # Локальное имя (маппится на Entity.Contract)
│       │           └── config.yaml   # То же что Contract_Number, но другое имя
│       │
│       └── Website/                  # Конфигурации источника Website
│           ├── source.yaml           # p: 0.5, key_label: "session_id"
│           └── labels/
│               ├── PageViews/
│               │   └── config.yaml   # data_type: "integer", analytics data
│               ├── SessionID/
│               │   └── config.yaml   # data_type: "string", ключевое поле
│               └── UserEmail/        # Локальное имя (маппится на Entity.Email)
│                   └── config.yaml   # data_type: "email", может отличаться от CRM.Email
│
├── tests/                            # Тесты (только в dev ветке)
│   ├── __init__.py
│   ├── conftest.py                   # Фикстуры pytest
│   │
│   ├── unit/                         # Юнит-тесты
│   │   ├── __init__.py
│   │   ├── test_cli/
│   │   │   ├── __init__.py
│   │   │   ├── test_parser.py
│   │   │   └── test_commands.py
│   │   │
│   │   ├── test_core/
│   │   │   ├── __init__.py
│   │   │   ├── test_api.py
│   │   │   └── test_orchestrator.py
│   │   │
│   │   ├── test_storage/
│   │   │   ├── __init__.py
│   │   │   ├── test_engine.py
│   │   │   ├── test_schema.py
│   │   │   └── test_transactions.py
│   │   │
│   │   ├── test_pools/
│   │   │   ├── __init__.py
│   │   │   ├── test_manager.py
│   │   │   ├── test_small_pool.py
│   │   │   └── test_large_pool.py
│   │   │
│   │   ├── test_loader/
│   │   │   ├── __init__.py
│   │   │   ├── test_json_loader.py
│   │   │   └── test_validator.py
│   │   │
│   │   ├── test_entities/            # НОВЫЙ: Тесты Entity Manager
│   │   │   ├── __init__.py
│   │   │   ├── test_manager.py       # Тесты управления сущностями
│   │   │   ├── test_mapper.py        # Тесты маппинга source → entity
│   │   │   └── test_validator.py     # Тесты валидации семантики
│   │   │
│   │   ├── test_processing/          # Расширенные тесты Processing Engine
│   │   │   ├── __init__.py
│   │   │   ├── test_engine.py        # Тесты координатора уровней
│   │   │   │
│   │   │   ├── test_single_source/   # НОВЫЙ: Тесты уровня 1
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_processor.py # Основной процессор источника
│   │   │   │   ├── test_time_resolver.py # Временные коллизии
│   │   │   │   ├── test_normalizer.py # Нормализация данных
│   │   │   │   └── test_rest_operations.py # REST API операции
│   │   │   │
│   │   │   ├── test_multi_source/    # НОВЫЙ: Тесты уровня 2
│   │   │   │   ├── __init__.py
│   │   │   │   ├── test_integrator.py # Интегратор источников
│   │   │   │   ├── test_conflict_resolver.py # Коллизии по весам
│   │   │   │   └── test_entity_merger.py # Объединение по сущностям
│   │   │   │
│   │   │   └── test_semantic/        # НОВЫЙ: Тесты семантического маппинга
│   │   │       ├── __init__.py
│   │   │       ├── test_mapper.py    # Семантический маппинг
│   │   │       └── test_entity_resolver.py # Разрешение конфликтов сущностей
│   │   │
│   │   ├── test_snapshots/           # Расширенные тесты Snapshot Manager
│   │   │   ├── __init__.py
│   │   │   ├── test_manager.py       # Основной менеджер
│   │   │   ├── test_builder.py       # Построение снэпшотов
│   │   │   ├── test_exporter.py      # Выгрузка в файлы
│   │   │   └── test_level_manager.py # НОВЫЙ: Координация уровней снэпшотов
│   │   │
│   │   ├── test_config/              # Расширенные тесты Config Manager
│   │   │   ├── __init__.py
│   │   │   ├── test_manager.py       # Координация конфигураций
│   │   │   ├── test_yaml_parser.py   # Парсинг YAML
│   │   │   ├── test_entity_config.py # НОВЫЙ: Конфиги сущностей
│   │   │   └── test_mapping_config.py # НОВЫЙ: Конфиги маппингов
│   │   │
│   │   ├── test_archive/             # Расширенные тесты Archive Manager
│   │   │   ├── __init__.py
│   │   │   ├── test_manager.py       # Управление архивом
│   │   │   ├── test_lifecycle.py     # Жизненный цикл данных
│   │   │   └── test_entity_aware_archive.py # НОВЫЙ: Entity-aware архивирование
│   │   │
│   │   └── test_utils/               # Расширенные тесты Utils
│   │       ├── __init__.py
│   │       ├── test_logging.py       # Логирование с контекстом
│   │       ├── test_exceptions.py    # Исключения для уровней
│   │       ├── test_helpers.py       # Общие функции
│   │       ├── test_semantic_utils.py # НОВЫЙ: Семантические утилиты
│   │       └── test_validation_utils.py # НОВЫЙ: Валидационные утилиты
│   │
│   ├── integration/                  # Интеграционные тесты (расширенные)
│   │   ├── __init__.py
│   │   ├── test_full_workflow.py     # Полный цикл работы (двухуровневый)
│   │   ├── test_single_source_pipeline.py # НОВЫЙ: Пайплайн уровня 1
│   │   ├── test_multi_source_pipeline.py  # НОВЫЙ: Пайплайн уровня 2
│   │   ├── test_entity_mapping_workflow.py # НОВЫЙ: Семантический маппинг
│   │   ├── test_archive_workflow.py  # Архивирование с учетом сущностей
│   │   └── test_snapshot_integration.py # НОВЫЙ: Интеграция снэпшотов
│   │
│   └── fixtures/                     # Тестовые данные (двухуровневые)
│       ├── sample_data/
│       │   ├── input_data.json       # Входные данные для тестов
│       │   ├── expected_output.json  # Ожидаемые результаты
│       │   ├── single_source_snapshots/  # НОВЫЙ: Снэпшоты уровня 1
│       │   │   ├── TestCRM_snapshot.json
│       │   │   └── TestERP_snapshot.json
│       │   └── integrated_snapshots/ # НОВЫЙ: Интегрированные снэпшоты
│       │       └── test_integrated_snapshot.json
│       │
│       ├── configs/                  # Тестовые конфигурации (многоуровневые)
│       │   └── sources/
│       │       │
│       │       ├── entities/         # НОВЫЙ: Тестовые сущности
│       │       │   ├── TestContract.yaml  # Тестовая сущность договора
│       │       │   ├── TestPrice.yaml     # Тестовая сущность цены
│       │       │   └── TestEmail.yaml     # Тестовая сущность email
│       │       │
│       │       ├── mappings/         # НОВЫЙ: Тестовые маппинги
│       │       │   ├── TestCRM_to_entities.yaml  # Маппинг TestCRM → entities
│       │       │   ├── TestERP_to_entities.yaml  # Маппинг TestERP → entities
│       │       │   └── test_global_mappings.yaml # Глобальные правила
│       │       │
│       │       ├── TestCRM/          # Тестовый источник CRM
│       │       │   ├── source.yaml   # p: 0.8, key_label: "test_customer_id"
│       │       │   └── labels/
│       │       │       ├── TestEmail/
│       │       │       │   └── config.yaml   # data_type: "email"
│       │       │       ├── TestCustomerID/
│       │       │       │   └── config.yaml   # data_type: "number", ключевое поле
│       │       │       └── TestContractNum/   # Маппится на TestContract
│       │       │           └── config.yaml   # data_type: "string"
│       │       │
│       │       └── TestERP/          # Тестовый источник ERP
│       │           ├── source.yaml   # p: 0.9, key_label: "test_product_id"
│       │           └── labels/
│       │               ├── TestProductID/
│       │               │   └── config.yaml   # data_type: "string", ключевое поле
│       │               ├── TestPrice/
│       │               │   └── config.yaml   # data_type: "decimal"
│       │               └── TestAgreementID/   # Маппится на TestContract
│       │                   └── config.yaml   # data_type: "string"
│       │
│       └── databases/                # Тестовые базы данных
│           ├── empty.db              # Пустая БД со схемой
│           ├── single_source_data.db # БД с данными уровня 1
│           ├── multi_source_data.db  # БД с данными уровня 2
│           └── full_sample_data.db   # Полная тестовая БД
│
├── sql/                              # SQL скрипты
│   ├── init_schema.sql               # Создание схемы БД
│   ├── indexes.sql                   # Создание индексов
│   └── views.sql                     # Создание VIEW
│
├── docs/                             # Документация (только в dev)
│   ├── architecture.md
│   ├── api_reference.md
│   ├── user_guide.md
│   └── development.md
│
├── examples/                         # Примеры использования
│   ├── basic_usage/
│   │   ├── data.json
│   │   ├── config.yaml
│   │   └── README.md
│   │
│   └── advanced_usage/
│       ├── multiple_sources.json
│       ├── configs/
│       │   └── sources/
│       └── README.md
│
└── scripts/                          # Вспомогательные скрипты (только в dev)
    ├── run_tests.py                  # Запуск тестов
    ├── init_dev_db.py                # Инициализация dev БД
    └── clean_build.py                # Очистка временных файлов
```

---

## Конфигурируемые пути

### Пути по умолчанию

```python
DEFAULT_PATHS = {
    "database": "./data/database.db",
    "configs": "./data/sources/",
    "snapshots": "./data/snapshots/"
}
```

### Способы переопределения

1. **Аргументы командной строки:**
   ```bash
   framework --database /custom/path/db.sqlite --configs /custom/configs/
   ```

2. **Переменные окружения:**
   ```bash
   export FRAMEWORK_DATABASE="/custom/path/db.sqlite"
   export FRAMEWORK_CONFIGS="/custom/configs/"
   ```

3. **Конфигурационный файл:**
   ```yaml
   # framework.yaml
   paths:
     database: "/custom/path/db.sqlite"
     configs: "/custom/configs/"
     snapshots: "/custom/snapshots/"
   ```

---

## Структура продакшн версии (ветка main)

При слиянии в `main` удаляются следующие директории:
- `tests/` — все тесты
- `docs/` — документация разработчика
- `scripts/` — вспомогательные скрипты разработки

Остается:
- `src/` — основной код
- `data/` — рабочие данные (с примерами конфигов)
- `sql/` — SQL скрипты
- `examples/` — примеры использования

---

## Особенности организации (Двухуровневая архитектура)

### 1. Двухуровневая модульность
- **Уровень 1 (Single Source):** Изолированная обработка каждого источника данных
- **Уровень 2 (Multi Source):** Интеграция и семантическое объединение источников
- Четкое разделение ответственности между уровнями
- Возможность независимого тестирования каждого уровня

### 2. Семантическая конфигурируемость
- **Source-level configs:** Конфигурации отдельных источников (`data/sources/CRM/`, `data/sources/ERP/`)
- **Entity-level configs:** Глобальные сущности (`data/sources/entities/`)
- **Mapping-level configs:** Семантические маппинги (`data/sources/mappings/`)
- Поддержка различных способов конфигурации (CLI, env, config файлы)
- Трехуровневая система путей (`database`, `configs`, `snapshots`)

### 3. Многоуровневая тестируемость
- **Unit tests:** Раздельные тесты для single_source и multi_source компонентов
- **Integration tests:** Тесты полных пайплайнов уровня 1 и 2
- **Entity mapping tests:** Специализированные тесты семантического маппинга
- Тестовые фикстуры с поддержкой двухуровневой архитектуры

### 4. Готовность к семантическому развертыванию
- Четкое разделение dev/prod версий с сохранением entity mappings
- SQL скрипты для инициализации со всеми уровнями
- Примеры конфигураций для различных сценариев маппинга
- Двухуровневые снэпшоты (source-level + integrated)

### 5. Семантическая расширяемость
- **Новые источники:** Легкое добавление через source configs + mappings
- **Новые сущности:** Декларативное определение в `entities/`
- **Новые маппинги:** Гибкая система правил в `mappings/`
- Архитектура готова к сложным семантическим преобразованиям

### 6. Конфликт-резолюция на двух уровнях
- **Уровень 1:** Временные коллизии (более поздние данные побеждают)
- **Уровень 2:** Коллизии по весам доверия + семантический анализ
- Прозрачность процесса разрешения конфликтов на каждом уровне

### 7. Workflow поддержка
- **Single Source Workflow:** Загрузка → Нормализация → REST API → Хранение
- **Multi Source Workflow:** Маппинг → Интеграция → Разрешение коллизий → Объединение
- **Entity Management Workflow:** Определение сущностей → Создание маппингов → Валидация