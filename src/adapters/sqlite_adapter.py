from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional, Tuple, Union

from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, ValId,
    Lb, Src, Transaction, TransactionInput,
)
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok
from src.persistence.mappers import lb_mapper, src_mapper, transaction_mapper
from src.persistence.records.lb_record import LbRecord
from src.persistence.records.src_record import SrcRecord
from src.persistence.records.transaction_record import TransactionRecord
from src.ports.clock_port import ClockPort
from src.adapters.system_ports import SystemClock

_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS acts (
    act_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name   TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS srcs (
    src_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    UNIQUE NOT NULL,
    description TEXT,
    p           REAL    NOT NULL DEFAULT 0.5,
    key_label   INTEGER,                        -- NULL until bootstrapped (see src_set_key_label)
    FOREIGN KEY (key_label) REFERENCES lbs(lb_id)
);

CREATE TABLE IF NOT EXISTS lbs (
    lb_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT,
    p           REAL    NOT NULL DEFAULT 0.5,
    src_id      INTEGER NOT NULL,                -- labels are source-specific
    UNIQUE (src_id, name),
    FOREIGN KEY (src_id) REFERENCES srcs(src_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ids (
    id_id INTEGER PRIMARY KEY AUTOINCREMENT,
    value TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS vals (
    val_id INTEGER PRIMARY KEY AUTOINCREMENT,
    value  TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS cnts (
    cnt_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    cnt INTEGER PRIMARY KEY,
    act INTEGER NOT NULL,
    dt  REAL    NOT NULL,
    src INTEGER NOT NULL,
    lb  INTEGER NOT NULL,
    id  INTEGER NOT NULL,
    val INTEGER,
    p   REAL    NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,          -- when the record was physically inserted (distinct from dt)
    FOREIGN KEY (cnt) REFERENCES cnts(cnt_id)        ON DELETE RESTRICT,
    FOREIGN KEY (act) REFERENCES acts(act_id)        ON DELETE RESTRICT,
    FOREIGN KEY (src) REFERENCES srcs(src_id)        ON DELETE RESTRICT,
    FOREIGN KEY (lb)  REFERENCES lbs(lb_id)          ON DELETE RESTRICT,
    FOREIGN KEY (id)  REFERENCES ids(id_id)          ON DELETE RESTRICT,
    FOREIGN KEY (val) REFERENCES vals(val_id)        ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS transactions_archive (
    cnt INTEGER PRIMARY KEY,
    act INTEGER NOT NULL,
    dt  REAL    NOT NULL,
    src INTEGER NOT NULL,
    lb  INTEGER NOT NULL,
    id  INTEGER NOT NULL,
    val INTEGER,
    p   REAL    NOT NULL DEFAULT 1.0,
    created_at REAL NOT NULL,
    FOREIGN KEY (cnt) REFERENCES cnts(cnt_id)        ON DELETE RESTRICT,
    FOREIGN KEY (act) REFERENCES acts(act_id)        ON DELETE RESTRICT,
    FOREIGN KEY (src) REFERENCES srcs(src_id)        ON DELETE RESTRICT,
    FOREIGN KEY (lb)  REFERENCES lbs(lb_id)          ON DELETE RESTRICT,
    FOREIGN KEY (id)  REFERENCES ids(id_id)          ON DELETE RESTRICT,
    FOREIGN KEY (val) REFERENCES vals(val_id)        ON DELETE RESTRICT
);


CREATE INDEX IF NOT EXISTS idx_txn_dt         ON transactions(dt);
CREATE INDEX IF NOT EXISTS idx_txn_src_lb_id  ON transactions(src, lb, id);
CREATE INDEX IF NOT EXISTS idx_arch_dt        ON transactions_archive(dt);
CREATE INDEX IF NOT EXISTS idx_arch_src_lb_id ON transactions_archive(src, lb, id);

CREATE VIEW IF NOT EXISTS transactions_full AS
    SELECT * FROM transactions
    UNION ALL
    SELECT * FROM transactions_archive;
"""


_SQLITE_MAX_VARS = 900  # stay comfortably under SQLite's bound-parameter limit


def _chunks(values: List[int], size: int) -> List[List[int]]:
    return [values[i:i + size] for i in range(0, len(values), size)] or [[]]


def _id_chunks(id_ids: Optional[List[int]]) -> List[Optional[List[int]]]:
    """None -> no id filter (single pass). Otherwise chunked to stay under
    SQLite's bound-parameter limit -- the one filter dimension a --where
    condition (see src/service/selector.py) can realistically make large;
    lb_ids/cnts come from explicit CLI flags and are assumed to stay small."""
    if id_ids is None:
        return [None]
    uniq = sorted({int(x) for x in id_ids})
    if not uniq:
        return [[]]  # explicitly empty (e.g. --where matched nothing) -> matches nothing
    return _chunks(uniq, _SQLITE_MAX_VARS)


def _filter_clauses(
    src_id: Optional[int],
    lb_ids: Optional[List[int]],
    id_ids: Optional[List[int]],
    cnts: Optional[List[int]],
    from_dt: Optional[float],
    until_dt: Optional[float],
    created_from: Optional[float],
    created_until: Optional[float],
) -> Tuple[List[str], List]:
    """Shared AND-ed WHERE fragments for txn_query/txn_archive/txn_delete. An
    explicitly empty list (as opposed to None) means "matches nothing" -- e.g.
    a --where condition that resolved to zero keys."""
    clauses: List[str] = []
    params: List = []

    def _in_clause(col: str, values: Optional[List[int]]) -> None:
        if values is None:
            return
        if not values:
            clauses.append("0=1")
            return
        clauses.append(f"{col} IN ({','.join('?' * len(values))})")
        params.extend(values)

    if src_id is not None:
        clauses.append("src = ?")
        params.append(src_id)
    _in_clause("lb", lb_ids)
    _in_clause("id", id_ids)
    _in_clause("cnt", cnts)
    if from_dt is not None:
        clauses.append("dt >= ?")
        params.append(from_dt)
    if until_dt is not None:
        clauses.append("dt <= ?")
        params.append(until_dt)
    if created_from is not None:
        clauses.append("created_at >= ?")
        params.append(created_from)
    if created_until is not None:
        clauses.append("created_at <= ?")
        params.append(created_until)
    return clauses, params


class SQLiteAdapter:
    def __init__(self, db_path: str, clock: ClockPort = None) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        self._conn.isolation_level = None  # autocommit; transactions managed explicitly
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._clock: ClockPort = clock if clock is not None else SystemClock()
        self._lb_cache: Dict[Tuple[int, str], int] = {}
        self._act_cache: Dict[str, int] = {}
        self._src_cache: Dict[str, int] = {}
        self._id_cache: Dict[str, int] = {}
        self._val_cache: Dict[str, int] = {}
        self._load_small_pools()

    def _load_small_pools(self) -> None:
        for row in self._conn.execute("SELECT src_id, name, lb_id FROM lbs"):
            self._lb_cache[(row[0], row[1])] = row[2]
        for row in self._conn.execute("SELECT name, act_id FROM acts"):
            self._act_cache[row[0]] = row[1]
        for row in self._conn.execute("SELECT name, src_id FROM srcs"):
            self._src_cache[row[0]] = row[1]
        for row in self._conn.execute("SELECT value, id_id FROM ids"):
            self._id_cache[row[0]] = row[1]

    # --- String pool operations ---

    def begin(self) -> None:
        self._conn.execute("BEGIN")

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def lb_intern(self, name: str, src_id: SrcId) -> Union[Ok[LbId], Err[StorageError]]:
        try:
            cache_key = (int(src_id), name)
            if cache_key in self._lb_cache:
                return Ok(LbId(self._lb_cache[cache_key]))
            self._conn.execute(
                "INSERT OR IGNORE INTO lbs (name, src_id) VALUES (?, ?)", (name, int(src_id))
            )
            row = self._conn.execute(
                "SELECT lb_id FROM lbs WHERE name = ? AND src_id = ?", (name, int(src_id))
            ).fetchone()
            lb_id = row[0]
            self._lb_cache[cache_key] = lb_id
            return Ok(LbId(lb_id))
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def id_intern(self, value: str) -> Union[Ok[IdId], Err[StorageError]]:
        try:
            if value in self._id_cache:
                return Ok(IdId(self._id_cache[value]))
            self._conn.execute(
                "INSERT OR IGNORE INTO ids (value) VALUES (?)", (value,)
            )
            row = self._conn.execute(
                "SELECT id_id FROM ids WHERE value = ?", (value,)
            ).fetchone()
            id_id = row[0]
            self._id_cache[value] = id_id
            return Ok(IdId(id_id))
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def id_get(self, id_id: IdId) -> Union[Ok[str], Err[StorageError]]:
        try:
            row = self._conn.execute(
                "SELECT value FROM ids WHERE id_id = ?", (int(id_id),)
            ).fetchone()
            if row is None:
                return Err(StorageError(f"id {id_id} not found"))
            return Ok(row[0])
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def id_lookup(self, value: str) -> Union[Ok[Optional[IdId]], Err[StorageError]]:
        """Reverse lookup, value -> IdId, WITHOUT creating an entry if it
        doesn't exist (unlike id_intern) -- for resolving --id VALUE the same
        way --src/--lb are resolved: unknown value is a NotFound, not a
        silently-created pool row."""
        try:
            if value in self._id_cache:
                return Ok(IdId(self._id_cache[value]))
            row = self._conn.execute(
                "SELECT id_id FROM ids WHERE value = ?", (value,)
            ).fetchone()
            if row is None:
                return Ok(None)
            self._id_cache[value] = row[0]
            return Ok(IdId(row[0]))
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def val_intern(self, value: str) -> Union[Ok[ValId], Err[StorageError]]:
        try:
            if value in self._val_cache:
                return Ok(ValId(self._val_cache[value]))
            self._conn.execute(
                "INSERT OR IGNORE INTO vals (value) VALUES (?)", (value,)
            )
            row = self._conn.execute(
                "SELECT val_id FROM vals WHERE value = ?", (value,)
            ).fetchone()
            val_id = row[0]
            self._val_cache[value] = val_id
            return Ok(ValId(val_id))
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def val_get(self, val_id: ValId) -> Union[Ok[str], Err[StorageError]]:
        try:
            row = self._conn.execute(
                "SELECT value FROM vals WHERE val_id = ?", (int(val_id),)
            ).fetchone()
            if row is None:
                return Err(StorageError(f"val {val_id} not found"))
            return Ok(row[0])
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def act_intern(self, act: Act) -> Union[Ok[ActId], Err[StorageError]]:
        try:
            name = act.value
            if name in self._act_cache:
                return Ok(ActId(self._act_cache[name]))
            self._conn.execute(
                "INSERT OR IGNORE INTO acts (name) VALUES (?)", (name,)
            )
            row = self._conn.execute(
                "SELECT act_id FROM acts WHERE name = ?", (name,)
            ).fetchone()
            act_id = row[0]
            self._act_cache[name] = act_id
            return Ok(ActId(act_id))
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    # --- Source metadata ---

    def src_get_or_create(
        self, name: str
    ) -> Union[Ok[Src], Err[StorageError]]:
        try:
            if name in self._src_cache:
                return self.src_get(SrcId(self._src_cache[name]))
            self._conn.execute(
                "INSERT OR IGNORE INTO srcs (name) VALUES (?)",
                (name,),
            )
            row = self._conn.execute(
                "SELECT src_id, name, description, p, key_label FROM srcs WHERE name = ?",
                (name,),
            ).fetchone()
            record = SrcRecord.from_row(row)
            self._src_cache[name] = record.src_id
            result = src_mapper.record_to_domain(record)
            if isinstance(result, Err):
                return Err(StorageError(result.error.message))
            return result
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def src_get(self, src_id: SrcId) -> Union[Ok[Src], Err[StorageError]]:
        try:
            row = self._conn.execute(
                "SELECT src_id, name, description, p, key_label FROM srcs WHERE src_id = ?",
                (int(src_id),),
            ).fetchone()
            if row is None:
                return Err(StorageError(f"src {src_id} not found"))
            result = src_mapper.record_to_domain(SrcRecord.from_row(row))
            if isinstance(result, Err):
                return Err(StorageError(result.error.message))
            return result
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def src_update(self, src: Src) -> Union[Ok[None], Err[StorageError]]:
        try:
            key_label = int(src.key_label) if src.key_label is not None else None
            self._conn.execute(
                "UPDATE srcs SET description = ?, p = ?, key_label = ? WHERE src_id = ?",
                (src.description, src.p, key_label, int(src.src_id)),
            )
            self._conn.commit()  # standalone call — commit immediately
            return Ok(None)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def src_set_key_label(
        self, src_id: SrcId, lb_id: LbId
    ) -> Union[Ok[None], Err[StorageError]]:
        try:
            self._conn.execute(
                "UPDATE srcs SET key_label = ? WHERE src_id = ?",
                (int(lb_id), int(src_id)),
            )
            self._conn.commit()  # standalone call — commit immediately
            return Ok(None)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def src_list(self) -> Union[Ok[List[Src]], Err[StorageError]]:
        try:
            rows = self._conn.execute(
                "SELECT src_id, name, description, p, key_label FROM srcs"
            ).fetchall()
            result: List[Src] = []
            for row in rows:
                mapped = src_mapper.record_to_domain(SrcRecord.from_row(row))
                if isinstance(mapped, Err):
                    return Err(StorageError(mapped.error.message))
                result.append(mapped.value)
            return Ok(result)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    # --- Label metadata ---

    def lb_get(self, lb_id: LbId) -> Union[Ok[Lb], Err[StorageError]]:
        try:
            row = self._conn.execute(
                "SELECT lb_id, name, description, p, src_id FROM lbs WHERE lb_id = ?",
                (int(lb_id),),
            ).fetchone()
            if row is None:
                return Err(StorageError(f"lb {lb_id} not found"))
            result = lb_mapper.record_to_domain(LbRecord.from_row(row))
            if isinstance(result, Err):
                return Err(StorageError(result.error.message))
            return result
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def lb_update(self, lb: Lb) -> Union[Ok[None], Err[StorageError]]:
        try:
            self._conn.execute(
                "UPDATE lbs SET description = ?, p = ? WHERE lb_id = ?",
                (lb.description, lb.p, int(lb.lb_id)),
            )
            self._conn.commit()  # standalone call — commit immediately
            return Ok(None)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def lb_list(self, src_id: Optional[SrcId] = None) -> Union[Ok[List[Lb]], Err[StorageError]]:
        try:
            if src_id is not None:
                rows = self._conn.execute(
                    "SELECT lb_id, name, description, p, src_id FROM lbs WHERE src_id = ?",
                    (int(src_id),),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT lb_id, name, description, p, src_id FROM lbs"
                ).fetchall()
            result: List[Lb] = []
            for row in rows:
                mapped = lb_mapper.record_to_domain(LbRecord.from_row(row))
                if isinstance(mapped, Err):
                    return Err(StorageError(mapped.error.message))
                result.append(mapped.value)
            return Ok(result)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def lb_merge(
        self, from_lb_id: LbId, into_lb_id: LbId,
    ) -> Union[Ok[int], Err[StorageError]]:
        try:
            self._conn.execute("BEGIN")
            into_src_id = self._conn.execute(
                "SELECT src_id FROM lbs WHERE lb_id = ?", (int(into_lb_id),)
            ).fetchone()[0]
            # fetched up front so the _lb_cache entry can be evicted below -- otherwise
            # a later lb_intern(old_name, old_src_id) (e.g. a stray `ds load` still using
            # the retired name) would resolve to the lb_id this call is about to delete
            from_src_id, from_name = self._conn.execute(
                "SELECT src_id, name FROM lbs WHERE lb_id = ?", (int(from_lb_id),)
            ).fetchone()
            moved = 0
            for table in ("transactions", "transactions_archive"):
                cur = self._conn.execute(
                    f"UPDATE {table} SET lb = ?, src = ? WHERE lb = ?",
                    (int(into_lb_id), into_src_id, int(from_lb_id)),
                )
                moved += cur.rowcount
            self._conn.execute("DELETE FROM lbs WHERE lb_id = ?", (int(from_lb_id),))
            self._conn.commit()
            self._lb_cache.pop((from_src_id, from_name), None)
            return Ok(moved)
        except sqlite3.Error as exc:
            self._conn.rollback()
            return Err(StorageError(str(exc)))

    # --- Transactions ---

    def txn_insert(
        self, txn: TransactionInput, archived: bool = False,
    ) -> Union[Ok[Transaction], Err[StorageError]]:
        try:
            table = "transactions_archive" if archived else "transactions"
            created_at = self._clock.now()
            cur = self._conn.execute("INSERT INTO cnts (created_at) VALUES (?)", (created_at,))
            cnt_id = cur.lastrowid
            self._conn.execute(
                f"INSERT INTO {table} (cnt, act, dt, src, lb, id, val, p, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cnt_id,
                    int(txn.act),
                    txn.dt,
                    int(txn.src),
                    int(txn.lb),
                    int(txn.id),
                    int(txn.val) or None,  # 0 → NULL in SQLite (DELETE semantics)
                    txn.p,
                    created_at,
                ),
            )
            result = transaction_mapper.record_to_domain(
                TransactionRecord(
                    cnt=cnt_id,
                    act=int(txn.act),
                    dt=txn.dt,
                    src=int(txn.src),
                    lb=int(txn.lb),
                    id=int(txn.id),
                    p=txn.p,
                    created_at=created_at,
                    val=int(txn.val) or None,  # 0 → NULL in SQLite (DELETE semantics)
                )
            )
            if isinstance(result, Err):
                return Err(StorageError(result.error.message))
            return result
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def txn_query(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
        from_cnt: Optional[CntId] = None,
        include_archive: bool = False,
    ) -> Union[Ok[List[Transaction]], Err[StorageError]]:
        try:
            table = "transactions_full" if include_archive else "transactions"
            lb_list = sorted({int(x) for x in lb_ids}) if lb_ids is not None else None
            cnt_list = sorted({int(x) for x in cnts}) if cnts is not None else None
            result: List[Transaction] = []
            for id_chunk in _id_chunks(list(id_ids) if id_ids is not None else None):
                clauses, params = _filter_clauses(
                    int(src_id) if src_id is not None else None,
                    lb_list, id_chunk, cnt_list,
                    from_dt, until_dt, created_from, created_until,
                )
                if from_cnt is not None:
                    clauses.append("cnt > ?")
                    params.append(int(from_cnt))
                where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
                rows = self._conn.execute(
                    f"SELECT cnt, act, dt, src, lb, id, val, p, created_at FROM {table} {where} ORDER BY cnt",
                    params,
                ).fetchall()
                for row in rows:
                    mapped = transaction_mapper.record_to_domain(TransactionRecord.from_row(row))
                    if isinstance(mapped, Err):
                        return Err(StorageError(mapped.error.message))
                    result.append(mapped.value)
            result.sort(key=lambda t: int(t.cnt))
            return Ok(result)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

    def txn_archive(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
    ) -> Union[Ok[int], Err[StorageError]]:
        try:
            self._conn.execute("BEGIN")
            lb_list = sorted({int(x) for x in lb_ids}) if lb_ids is not None else None
            cnt_list = sorted({int(x) for x in cnts}) if cnts is not None else None
            moved = 0
            for id_chunk in _id_chunks(list(id_ids) if id_ids is not None else None):
                clauses, params = _filter_clauses(
                    int(src_id) if src_id is not None else None,
                    lb_list, id_chunk, cnt_list,
                    from_dt, until_dt, created_from, created_until,
                )
                where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
                cur = self._conn.execute(
                    "INSERT INTO transactions_archive "
                    "SELECT cnt, act, dt, src, lb, id, val, p, created_at "
                    f"FROM transactions {where}",
                    params,
                )
                moved += cur.rowcount
                self._conn.execute(f"DELETE FROM transactions {where}", params)
            self._conn.commit()
            return Ok(moved)
        except sqlite3.Error as exc:
            self._conn.rollback()
            return Err(StorageError(str(exc)))

    def txn_unarchive(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
    ) -> Union[Ok[int], Err[StorageError]]:
        try:
            self._conn.execute("BEGIN")
            lb_list = sorted({int(x) for x in lb_ids}) if lb_ids is not None else None
            cnt_list = sorted({int(x) for x in cnts}) if cnts is not None else None
            moved = 0
            for id_chunk in _id_chunks(list(id_ids) if id_ids is not None else None):
                clauses, params = _filter_clauses(
                    int(src_id) if src_id is not None else None,
                    lb_list, id_chunk, cnt_list,
                    from_dt, until_dt, created_from, created_until,
                )
                where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
                cur = self._conn.execute(
                    "INSERT INTO transactions "
                    "SELECT cnt, act, dt, src, lb, id, val, p, created_at "
                    f"FROM transactions_archive {where}",
                    params,
                )
                moved += cur.rowcount
                self._conn.execute(f"DELETE FROM transactions_archive {where}", params)
            self._conn.commit()
            return Ok(moved)
        except sqlite3.Error as exc:
            self._conn.rollback()
            return Err(StorageError(str(exc)))

    def txn_delete(
        self,
        src_id: Optional[SrcId] = None,
        lb_ids: Optional[List[LbId]] = None,
        id_ids: Optional[List[IdId]] = None,
        cnts: Optional[List[CntId]] = None,
        from_dt: Optional[float] = None,
        until_dt: Optional[float] = None,
        created_from: Optional[float] = None,
        created_until: Optional[float] = None,
    ) -> Union[Ok[int], Err[StorageError]]:
        try:
            self._conn.execute("BEGIN")
            lb_list = sorted({int(x) for x in lb_ids}) if lb_ids is not None else None
            cnt_list = sorted({int(x) for x in cnts}) if cnts is not None else None
            deleted = 0
            for id_chunk in _id_chunks(list(id_ids) if id_ids is not None else None):
                clauses, params = _filter_clauses(
                    int(src_id) if src_id is not None else None,
                    lb_list, id_chunk, cnt_list,
                    from_dt, until_dt, created_from, created_until,
                )
                where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
                cur1 = self._conn.execute(f"DELETE FROM transactions {where}", params)
                cur2 = self._conn.execute(f"DELETE FROM transactions_archive {where}", params)
                # both tables count toward the total: a hard delete must account for
                # rows in the archive too, not just the active table
                deleted += cur1.rowcount + cur2.rowcount
            self._conn.commit()
            return Ok(deleted)
        except sqlite3.Error as exc:
            self._conn.rollback()
            return Err(StorageError(str(exc)))

    # --- Bulk history lookup ---

    def txn_last_values(
        self,
        src_id: SrcId,
        lb_ids: List[LbId],
        id_ids: List[IdId],
    ) -> Union[Ok[Dict[Tuple[LbId, IdId], ValId]], Err[StorageError]]:
        lb_list = sorted({int(x) for x in lb_ids})
        id_list = sorted({int(x) for x in id_ids})
        if not lb_list or not id_list:
            return Ok({})
        try:
            result: Dict[Tuple[LbId, IdId], ValId] = {}
            for lb_chunk in _chunks(lb_list, _SQLITE_MAX_VARS):
                if not lb_chunk:
                    continue
                for id_chunk in _chunks(id_list, _SQLITE_MAX_VARS):
                    if not id_chunk:
                        continue
                    lb_ph = ",".join("?" * len(lb_chunk))
                    id_ph = ",".join("?" * len(id_chunk))
                    rows = self._conn.execute(
                        f"""
                        SELECT t.lb, t.id, t.val
                        FROM transactions_full t
                        JOIN (
                            SELECT lb, id, MAX(cnt) AS mx
                            FROM transactions_full
                            WHERE src = ? AND lb IN ({lb_ph}) AND id IN ({id_ph})
                            GROUP BY lb, id
                        ) last ON t.lb = last.lb AND t.id = last.id AND t.cnt = last.mx
                        WHERE t.src = ?
                        """,
                        [int(src_id), *lb_chunk, *id_chunk, int(src_id)],
                    ).fetchall()
                    for lb, id_, val in rows:
                        result[(LbId(lb), IdId(id_))] = ValId(val or 0)
            return Ok(result)
        except sqlite3.Error as exc:
            return Err(StorageError(str(exc)))

