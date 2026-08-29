# ds

**Встраиваемый движок хранения историзированных данных из разнородных источников** и набор
инструментов инженера данных для работы с ним.

`ds` принимает периодические плоские выгрузки из систем-источников (CRM, ERP, отчёты), хранит
все изменения как неизменяемый журнал с атрибуцией «кто, что, когда сообщил» и позволяет
восстановить состояние данных на любой момент времени.

Это **нижний слой** (система записи): семантическая обработка, разрешение противоречий между
источниками и пользовательские интерфейсы — задача вышестоящего слоя и в этот репозиторий
не входят. Подробнее — [`docs/explanation/scope-and-non-goals.md`](docs/explanation/scope-and-non-goals.md).

## Статус

Альфа (`0.5.0a1` + `ds get`). Работает: загрузка колоночного JSON (`ds load`) с
автоопределением операции; выгрузка состояния источника на дату (`ds get`, свёртка Level 1,
пресеты); event-sourcing схема, партиционирование основной/архивной таблиц, два адаптера
хранилища.

Пока не реализовано (в scope, см. [`docs/roadmap/`](docs/roadmap/)): управление сущностями
схемы (merge/split), жизненный цикл в CLI (`archive`/`delete`), миграции, оптимизация.

## Быстрый старт

```bash
pip install -e .

mkdir -p sources/CRM
echo '{"name": "CRM", "key_label": "customer_id"}' > sources/CRM/source.json

cat > batch.json <<'JSON'
{ "customer_id": ["101","102"], "email": ["a@ex.com","b@ex.com"] }
JSON

ds --db data.db load sources/CRM batch.json --dt 1704067200
# loaded 2 transaction(s)
```

Полный сценарий — [`docs/guides/getting-started.md`](docs/guides/getting-started.md).
Запускаемые примеры — [`examples/`](examples/).

## Документация

Точка входа — [`docs/README.md`](docs/README.md).

| Раздел | Что внутри |
|---|---|
| [`docs/explanation/`](docs/explanation/) | зачем репозиторий и почему такие технические решения |
| [`docs/reference/`](docs/reference/) | как устроено сейчас, строго по коду (схема БД, CLI, форматы, порт) |
| [`docs/guides/`](docs/guides/) | руководства: установка, загрузка, чтение состояния через SQL |
| [`docs/decisions/`](docs/decisions/) | журнал архитектурных решений (ADR) |
| [`docs/roadmap/`](docs/roadmap/) | что ещё сядет в ядро |
| [`docs/attic/`](docs/attic/) | первоначальный замысел ноября 2025 — **не соответствует коду** |

## Разработка

Тесты гоняются в Docker на Python 3.9.20:

```bash
./run_tests.sh
```

См. [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Лицензия

См. [`LICENSE`](LICENSE).
