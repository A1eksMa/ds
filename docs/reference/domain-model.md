# Доменная модель (как в коде)

`src/domain/` — чистые типы без ввода-вывода. Всё — `@dataclass(frozen=True)`.

## Целочисленные ключи (`entities.py`)

`typing.NewType` поверх `int` — ссылки на пулы:

| Тип | Пул |
|---|---|
| `SrcId` | `srcs.src_id` |
| `LbId`  | `lbs.lb_id` |
| `IdId`  | `ids.id_id` |
| `ValId` | `vals.val_id` (`ValId(0)` = `DELETE`, реальные id с 1) |
| `ActId` | `acts.act_id` |
| `CntId` | `cnts.cnt_id` |

## `Src`

```python
@dataclass(frozen=True)
class Src:
    src_id: SrcId
    name: str
    p: float
    key_label: Optional[LbId]   # None до бутстрапа (src_set_key_label)
    description: Optional[str] = None
```

`key_label` опционален из-за циклической зависимости `Src` ↔ `Lb` —
[`../explanation/source-specific-labels.md`](../explanation/source-specific-labels.md).

## `Lb`

```python
@dataclass(frozen=True)
class Lb:
    lb_id: LbId
    name: str
    p: float
    src: SrcId                  # метка специфична для источника
    description: Optional[str] = None
```

## `TransactionInput` — что передаёт вызывающая сторона

```python
@dataclass(frozen=True)
class TransactionInput:
    act: ActId
    dt: float
    src: SrcId
    lb: LbId
    id: IdId
    p: float
    val: ValId = ValId(0)       # 0 = DELETE
```

`cnt` и `created_at` вызывающая сторона **не** задаёт — их присваивает хранилище.

## `Transaction` — что лежит в БД

```python
@dataclass(frozen=True)
class Transaction:
    cnt: CntId
    act: ActId
    dt: float
    src: SrcId
    lb: LbId
    id: IdId
    p: float
    created_at: float           # присвоено хранилищем
    val: ValId = ValId(0)
```

## `Act` (`enums.py`)

```python
class Act(str, Enum):
    POST = "POST"
    GET = "GET"        # зарезервирован, при загрузке не пишется
    PATCH = "PATCH"
    DELETE = "DELETE"
```

Семантика и авто-выбор — [`../explanation/act-semantics.md`](../explanation/act-semantics.md).

## `Result` (`result.py`)

```python
Ok(value=...)      .and_then(f) -> f(value)     .map(f) -> Ok(f(value))
Err(error=...)     .and_then(f) -> self         .map(f) -> self
```

Все операции портов и сервисов возвращают `Ok[...] | Err[...]`, исключения не бросаются
(кроме программных ошибок). Проверка — `isinstance(result, Err)`.

## Ошибки (`errors.py`)

| Тип | Поля | Когда |
|---|---|---|
| `NotFound` | `entity`, `key` | сущность не найдена по имени/ключу |
| `AlreadyExists` | `entity`, `key` | нарушение уникальности на прикладном уровне |
| `ValidationError` | `field`, `message` | вход не прошёл проверку формы/диапазона |
| `StorageError` | `message` | ошибка ввода-вывода / SQLite / парсинга JSON |
| `IntegrityError` | `message` | нарушение целостности на уровне хранилища |

Псевдонимы: `DomainError = NotFound | AlreadyExists | ValidationError`;
`ServiceError = DomainError | StorageError | IntegrityError`.

Как ошибки превращаются в текст и коды возврата CLI — [`errors.md`](errors.md).
