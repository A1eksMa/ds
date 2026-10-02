# Примеры использования `ds`

Каждая папка — самодостаточный сценарий: фикстуры (`source.json`, файлы данных) + `run.sh`,
который прогоняет `ds` на них, + `expected/` с эталонным результатом.

Примеры служат трём целям:
1. **обучение** — посмотреть на живой сценарий и повторить;
2. **регрессионные тесты** — `tests/examples/test_examples.py` прогоняет каждый `run.sh` и
   сверяет вывод с `expected/`;
3. **основа для будущих тестов** — когда появится `ds get` / свёртка, `expected/` дополнится
   ожидаемым состоянием.

## Запуск вручную

```bash
bash examples/01-basic-load/run.sh /tmp/ex01     # data.db окажется в /tmp/ex01/
sqlite3 /tmp/ex01/data.db "SELECT * FROM transactions;"
```

`run.sh WORKDIR` кладёт `data.db` в `WORKDIR` (по умолчанию — временная папка, путь печатается
в stderr). Переопределить команду: `DS='ds' bash examples/01-basic-load/run.sh` (по умолчанию
`python3 -m src.cli.commands`, работает из корня репозитория без установки пакета).

## Как гоняются тесты

```bash
./run_tests.sh                                   # в Docker (Python 3.9.20), весь tests/
python -m pytest tests/examples/ -q              # локально, если установлен pytest
UPDATE_EXAMPLES=1 python -m pytest tests/examples/ -q   # перегенерировать expected/ после осознанной правки
```

Сверяется два артефакта на пример:
- `expected/stdout.txt` — дословный stdout `run.sh` (сообщения CLI);
- `expected/journal.txt` — человекочитаемый дамп журнала транзакций **без** поля `created_at`
  (оно недетерминированно — реальное время вставки).

## Каталог

| Пример | Показывает |
|---|---|
| [`01-basic-load`](01-basic-load/) | загрузка двух батчей, `PATCH` при первом появлении |
| [`02-partial-updates`](02-partial-updates/) | `POST` (перезапись) vs `PATCH` (новый объект) в одном батче |
| [`03-delete-semantics`](03-delete-semantics/) | `null` → `DELETE`, затем повторное появление → `PATCH` |
| [`04-get`](04-get/) | свёртка журнала в состояние на заданную дату, `ds get` |
| [`05-delete-label`](05-delete-label/) | `ds delete` — жёсткое удаление показателя из журнала (обе таблицы) |
| [`06-label-config`](06-label-config/) | инвентарь показателей в `source.json` — `type`/`archive`/`publish` |
| [`07-archive-where`](07-archive-where/) | `ds archive`/`ds delete` по условию на значение показателя (`--where LB=VALUE`) |
| [`08-compact`](08-compact/) | `ds compact` — убрать записи, повторяющие уже действовавшее значение |
| [`09-update-config`](09-update-config/) | `ds update` — синхронизировать инвентарь показателей `source.json` с базой |
| [`10-upload-strict`](10-upload-strict/) | `ds upload` — строгая загрузка: отказ целиком при новом показателе или несовпадении типа |
| [`11-unarchive-where`](11-unarchive-where/) | `ds unarchive` — зеркало `ds archive`: вернуть архивные транзакции обратно, тот же `--where` |
