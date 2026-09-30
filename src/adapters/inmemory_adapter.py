from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, ValId,
    Lb, Src, Transaction, TransactionInput,
)
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok
from src.ports.clock_port import ClockPort
from src.adapters.system_ports import SystemClock


def _row_matcher(
    src_id, lb_ids, id_ids, cnts, from_dt, until_dt, created_from, created_until,
):
    """Build a per-row predicate once (mirrors SQLiteAdapter's _filter_clauses):
    None = no filter on that dimension, an explicitly empty list = matches
    nothing (e.g. a --where condition that resolved to zero keys)."""
    lb_set = {int(x) for x in lb_ids} if lb_ids is not None else None
    id_set = {int(x) for x in id_ids} if id_ids is not None else None
    cnt_set = {int(x) for x in cnts} if cnts is not None else None

    def matches(row: Dict) -> bool:
        if src_id is not None and row["src"] != int(src_id):
            return False
        if lb_set is not None and row["lb"] not in lb_set:
            return False
        if id_set is not None and row["id"] not in id_set:
            return False
        if cnt_set is not None and row["cnt"] not in cnt_set:
            return False
        if from_dt is not None and row["dt"] < from_dt:
            return False
        if until_dt is not None and row["dt"] > until_dt:
            return False
        if created_from is not None and row["created_at"] < created_from:
            return False
        if created_until is not None and row["created_at"] > created_until:
            return False
        return True

    return matches


class InMemoryAdapter:
    """In-memory StoragePort implementation for testing."""

    def __init__(self, clock: ClockPort = None) -> None:
        self._clock: ClockPort = clock if clock is not None else SystemClock()

        self._lbs: Dict[int, Dict] = {}
        self._lb_names: Dict[Tuple[int, str], int] = {}  # (src_id, name) -> lb_id
        self._lb_seq = 0

        self._acts: Dict[int, str] = {}
        self._act_names: Dict[str, int] = {}
        self._act_seq = 0

        self._srcs: Dict[int, Dict] = {}
        self._src_names: Dict[str, int] = {}
        self._src_seq = 0

        self._ids: Dict[int, str] = {}
        self._id_values: Dict[str, int] = {}
        self._id_seq = 0

        self._vals: Dict[int, str] = {}
        self._val_values: Dict[str, int] = {}
        self._val_seq = 0

        self._cnt_seq = 0
        self._transactions: List[Dict] = []
        self._archive: List[Dict] = []

    def _next_lb(self) -> int:
        self._lb_seq += 1
        return self._lb_seq

    def _next_act(self) -> int:
        self._act_seq += 1
        return self._act_seq

    def _next_src(self) -> int:
        self._src_seq += 1
        return self._src_seq

    def _next_id(self) -> int:
        self._id_seq += 1
        return self._id_seq

    def _next_val(self) -> int:
        self._val_seq += 1
        return self._val_seq

    def _next_cnt(self) -> int:
        self._cnt_seq += 1
        return self._cnt_seq

    # --- Transaction control (no-op for in-memory) ---
    def begin(self) -> None: pass
    def commit(self) -> None: pass
    def rollback(self) -> None: pass

    # --- String pool operations ---

    def lb_intern(self, name: str, src_id: SrcId) -> Union[Ok[LbId], Err[StorageError]]:
        cache_key = (int(src_id), name)
        if cache_key not in self._lb_names:
            lb_id = self._next_lb()
            self._lb_names[cache_key] = lb_id
            self._lbs[lb_id] = {
                "lb_id": lb_id, "name": name, "p": 0.5, "src": int(src_id), "description": None,
            }
        return Ok(LbId(self._lb_names[cache_key]))

    def id_intern(self, value: str) -> Union[Ok[IdId], Err[StorageError]]:
        if value not in self._id_values:
            id_id = self._next_id()
            self._id_values[value] = id_id
            self._ids[id_id] = value
        return Ok(IdId(self._id_values[value]))

    def id_get(self, id_id: IdId) -> Union[Ok[str], Err[StorageError]]:
        value = self._ids.get(int(id_id))
        if value is None:
            return Err(StorageError(f"id {id_id} not found"))
        return Ok(value)

    def id_lookup(self, value: str) -> Union[Ok[Optional[IdId]], Err[StorageError]]:
        id_id = self._id_values.get(value)
        return Ok(IdId(id_id) if id_id is not None else None)

    def val_intern(self, value: str) -> Union[Ok[ValId], Err[StorageError]]:
        if value not in self._val_values:
            val_id = self._next_val()
            self._val_values[value] = val_id
            self._vals[val_id] = value
        return Ok(ValId(self._val_values[value]))

    def val_get(self, val_id: ValId) -> Union[Ok[str], Err[StorageError]]:
        value = self._vals.get(int(val_id))
        if value is None:
            return Err(StorageError(f"val {val_id} not found"))
        return Ok(value)

    def act_intern(self, act: Act) -> Union[Ok[ActId], Err[StorageError]]:
        name = act.value
        if name not in self._act_names:
            act_id = self._next_act()
            self._act_names[name] = act_id
            self._acts[act_id] = name
        return Ok(ActId(self._act_names[name]))

    # --- Source metadata ---

    def src_get_or_create(
        self, name: str
    ) -> Union[Ok[Src], Err[StorageError]]:
        if name not in self._src_names:
            src_id = self._next_src()
            self._src_names[name] = src_id
            self._srcs[src_id] = {
                "src_id": src_id, "name": name, "p": 0.5,
                "key_label": None, "description": None,
            }
        return self.src_get(SrcId(self._src_names[name]))

    def src_get(self, src_id: SrcId) -> Union[Ok[Src], Err[StorageError]]:
        data = self._srcs.get(int(src_id))
        if data is None:
            return Err(StorageError(f"src {src_id} not found"))
        key_label = data["key_label"]
        return Ok(Src(
            src_id=SrcId(data["src_id"]),
            name=data["name"],
            p=data["p"],
            key_label=LbId(key_label) if key_label is not None else None,
            description=data["description"],
        ))

    def src_update(self, src: Src) -> Union[Ok[None], Err[StorageError]]:
        if int(src.src_id) not in self._srcs:
            return Err(StorageError(f"src {src.src_id} not found"))
        key_label = int(src.key_label) if src.key_label is not None else None
        self._srcs[int(src.src_id)].update(
            {"p": src.p, "description": src.description, "key_label": key_label}
        )
        return Ok(None)

    def src_set_key_label(
        self, src_id: SrcId, lb_id: LbId
    ) -> Union[Ok[None], Err[StorageError]]:
        if int(src_id) not in self._srcs:
            return Err(StorageError(f"src {src_id} not found"))
        self._srcs[int(src_id)]["key_label"] = int(lb_id)
        return Ok(None)

    def src_list(self) -> Union[Ok[List[Src]], Err[StorageError]]:
        result = []
        for data in self._srcs.values():
            key_label = data["key_label"]
            result.append(Src(
                src_id=SrcId(data["src_id"]),
                name=data["name"],
                p=data["p"],
                key_label=LbId(key_label) if key_label is not None else None,
                description=data["description"],
            ))
        return Ok(result)

    # --- Label metadata ---

    def lb_get(self, lb_id: LbId) -> Union[Ok[Lb], Err[StorageError]]:
        data = self._lbs.get(int(lb_id))
        if data is None:
            return Err(StorageError(f"lb {lb_id} not found"))
        return Ok(Lb(
            lb_id=LbId(data["lb_id"]),
            name=data["name"],
            p=data["p"],
            src=SrcId(data["src"]),
            description=data["description"],
        ))

    def lb_update(self, lb: Lb) -> Union[Ok[None], Err[StorageError]]:
        if int(lb.lb_id) not in self._lbs:
            return Err(StorageError(f"lb {lb.lb_id} not found"))
        self._lbs[int(lb.lb_id)].update({"p": lb.p, "description": lb.description})
        return Ok(None)

    def lb_list(self, src_id: Optional[SrcId] = None) -> Union[Ok[List[Lb]], Err[StorageError]]:
        result = []
        for data in self._lbs.values():
            if src_id is not None and data["src"] != int(src_id):
                continue
            result.append(Lb(
                lb_id=LbId(data["lb_id"]),
                name=data["name"],
                p=data["p"],
                src=SrcId(data["src"]),
                description=data["description"],
            ))
        return Ok(result)

    # --- Transactions ---

    def txn_insert(
        self, txn: TransactionInput, archived: bool = False,
    ) -> Union[Ok[Transaction], Err[StorageError]]:
        cnt = CntId(self._next_cnt())
        created_at = self._clock.now()
        row = {
            "cnt": int(cnt), "act": int(txn.act), "dt": txn.dt,
            "src": int(txn.src), "lb": int(txn.lb), "id": int(txn.id),
            "val": int(txn.val),
            "p": txn.p,
            "created_at": created_at,
        }
        (self._archive if archived else self._transactions).append(row)
        return Ok(Transaction(
            cnt=cnt, act=txn.act, dt=txn.dt,
            src=txn.src, lb=txn.lb, id=txn.id,
            p=txn.p, created_at=created_at, val=txn.val,
        ))

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
        matches = _row_matcher(
            src_id, lb_ids, id_ids, cnts, from_dt, until_dt, created_from, created_until,
        )
        pool = self._transactions + (self._archive if include_archive else [])
        result = []
        for row in sorted(pool, key=lambda r: r["cnt"]):
            if not matches(row):
                continue
            if from_cnt is not None and row["cnt"] <= int(from_cnt):
                continue
            result.append(Transaction(
                cnt=CntId(row["cnt"]), act=ActId(row["act"]), dt=row["dt"],
                src=SrcId(row["src"]), lb=LbId(row["lb"]), id=IdId(row["id"]),
                p=row["p"], created_at=row["created_at"], val=ValId(row["val"]),
            ))
        return Ok(result)

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
        matches = _row_matcher(
            src_id, lb_ids, id_ids, cnts, from_dt, until_dt, created_from, created_until,
        )
        to_move = [r for r in self._transactions if matches(r)]
        self._archive.extend(to_move)
        self._transactions = [r for r in self._transactions if not matches(r)]
        return Ok(len(to_move))

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
        matches = _row_matcher(
            src_id, lb_ids, id_ids, cnts, from_dt, until_dt, created_from, created_until,
        )
        # both tables count toward the total: a hard delete must account for
        # rows in the archive too, not just the active list
        before = len(self._transactions) + len(self._archive)
        self._transactions = [r for r in self._transactions if not matches(r)]
        self._archive = [r for r in self._archive if not matches(r)]
        after = len(self._transactions) + len(self._archive)
        return Ok(before - after)

    # --- Bulk history lookup ---

    def txn_last_values(
        self,
        src_id: SrcId,
        lb_ids: List[LbId],
        id_ids: List[IdId],
    ) -> Union[Ok[Dict[Tuple[LbId, IdId], ValId]], Err[StorageError]]:
        lb_set = {int(x) for x in lb_ids}
        id_set = {int(x) for x in id_ids}
        last: Dict[Tuple[int, int], Dict] = {}
        for row in self._transactions + self._archive:
            if row["src"] != int(src_id):
                continue
            key = (row["lb"], row["id"])
            if key[0] not in lb_set or key[1] not in id_set:
                continue
            if key not in last or row["cnt"] > last[key]["cnt"]:
                last[key] = row
        return Ok({
            (LbId(lb), IdId(id_)): ValId(row["val"])
            for (lb, id_), row in last.items()
        })
