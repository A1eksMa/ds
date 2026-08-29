# `StoragePort` — контракт хранилища (как в коде)

`src/ports/storage_port.py` — `typing.Protocol` (`@runtime_checkable`). Весь доступ к данным
идёт через него. Две реализации: `SQLiteAdapter` (рабочая) и `InMemoryAdapter` (тесты).

Все методы, кроме управления транзакцией, возвращают `Ok[...] | Err[StorageError]`.

## Управление транзакцией

| Метод | Смысл |
|---|---|
| `begin()` | открыть транзакцию БД |
| `commit()` | зафиксировать |
| `rollback()` | откатить |

`service/load.py` оборачивает весь батч: `begin()` → работа → `commit()`, на любой `Err` —
`rollback()` и возврат ошибки.

## Интернирование строк (пулы)

«Строка → её целочисленный id, создать если нет».

| Метод | Возвращает |
|---|---|
| `lb_intern(name, src_id)` | `LbId` — метка **в контексте источника** (`src_id` обязателен) |
| `id_intern(value)` | `IdId` |
| `id_get(id_id)` | `str` — обратный резолв |
| `val_intern(value)` | `ValId` |
| `val_get(val_id)` | `str` |
| `act_intern(act: Act)` | `ActId` |

## Метаданные источника

| Метод | Смысл |
|---|---|
| `src_get_or_create(name)` | найти или создать `Src` (создаётся с `key_label = None`) |
| `src_get(src_id)` | `Src` по id |
| `src_update(src)` | перезаписать метаданные (`p`, `description`, ...) |
| `src_list()` | `List[Src]` — все источники (используется для резолва фильтра по имени без побочных эффектов) |
| `src_set_key_label(src_id, lb_id)` | бутстрап: дозаписать `srcs.key_label` после создания ключевой метки |

## Метаданные показателя

| Метод | Смысл |
|---|---|
| `lb_get(lb_id)` | `Lb` по id |
| `lb_update(lb)` | перезаписать метаданные метки |
| `lb_list(src_id=None)` | `List[Lb]`; с `src_id` — только метки этого источника |

## Транзакции

| Метод | Смысл |
|---|---|
| `txn_insert(TransactionInput)` | вставить запись; вернуть полный `Transaction` (с присвоенными `cnt`, `created_at`) |
| `txn_query(src_id=None, lb_id=None, id_id=None, until_dt=None, from_cnt=None, include_archive=False)` | выборка журнала с фильтрами; `until_dt` — срез «машины времени»; `from_cnt` — с какого `cnt`; `include_archive` — читать `transactions_full` |
| `txn_archive(until_dt)` | переместить в архив все транзакции с `dt <= until_dt`; вернуть число перемещённых |
| `txn_delete(src_id, lb_id=None)` | физически удалить транзакции источника (опц. одной метки); вернуть число удалённых |
| `txn_last_values(src_id, lb_ids, id_ids)` | для каждой пары `(lb, id)`, у которой есть хоть одна транзакция (активная или архивная) под `src_id`, — последнее `val` по `cnt`. Пары без истории в результат **не попадают**; вызывающий трактует отсутствие ключа как `val = 0`. Используется для авто-`act` при загрузке |

## Паритет адаптеров

`SQLiteAdapter` и `InMemoryAdapter` реализуют **один и тот же** контракт; часть набора тестов
(`tests/`) параметризуется обоими, чтобы поведение не расходилось. `InMemoryAdapter` — не
«урезанный», а полноценная альтернативная реализация для быстрых тестов без файла.

## `ClockPort`

`src/ports/clock_port.py`: `now() -> float` (Unix-время, секунды). Реализация по умолчанию —
`SystemClock` (`time.time`). `SQLiteAdapter.__init__(db_path, clock=None)` принимает подмену —
так `created_at` делается детерминированным в тестах.
