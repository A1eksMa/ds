from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Union

from src.domain.entities import (
    ActId, CntId, IdId, LbId, SrcId, ValId,
    Lb, Src, Transaction, TransactionInput,
)
from src.domain.enums import Act
from src.domain.errors import StorageError
from src.domain.result import Err, Ok


class InMemoryAdapter:
    """In-memory StoragePort implementation for testing."""

    def __init__(self) -> None:
        self._lbs: Dict[int, Dict] = {}
        self._lb_names: Dict[str, int] = {}
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

    def lb_intern(self, name: str) -> Union[Ok[LbId], Err[StorageError]]:
        if name not in self._lb_names:
            lb_id = self._next_lb()
            self._lb_names[name] = lb_id
            self._lbs[lb_id] = {"lb_id": lb_id, "name": name, "p": 0.5, "description": None}
        return Ok(LbId(self._lb_names[name]))

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
        self, name: str, key_label_id: LbId
    ) -> Union[Ok[Src], Err[StorageError]]:
        if name not in self._src_names:
            src_id = self._next_src()
            self._src_names[name] = src_id
            self._srcs[src_id] = {
                "src_id": src_id, "name": name, "p": 0.5,
                "key_label": int(key_label_id), "description": None,
            }
        return self.src_get(SrcId(self._src_names[name]))

    def src_get(self, src_id: SrcId) -> Union[Ok[Src], Err[StorageError]]:
        data = self._srcs.get(int(src_id))
        if data is None:
            return Err(StorageError(f"src {src_id} not found"))
        return Ok(Src(
            src_id=SrcId(data["src_id"]),
            name=data["name"],
            p=data["p"],
            key_label=LbId(data["key_label"]),
            description=data["description"],
        ))

    def src_update(self, src: Src) -> Union[Ok[None], Err[StorageError]]:
        if int(src.src_id) not in self._srcs:
            return Err(StorageError(f"src {src.src_id} not found"))
        self._srcs[int(src.src_id)].update(
            {"p": src.p, "description": src.description, "key_label": int(src.key_label)}
        )
        return Ok(None)

    def src_list(self) -> Union[Ok[List[Src]], Err[StorageError]]:
        result = []
        for data in self._srcs.values():
            result.append(Src(
                src_id=SrcId(data["src_id"]),
                name=data["name"],
                p=data["p"],
                key_label=LbId(data["key_label"]),
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
            description=data["description"],
        ))

    def lb_update(self, lb: Lb) -> Union[Ok[None], Err[StorageError]]:
        if int(lb.lb_id) not in self._lbs:
            return Err(StorageError(f"lb {lb.lb_id} not found"))
        self._lbs[int(lb.lb_id)].update({"p": lb.p, "description": lb.description})
        return Ok(None)

    def lb_list(self) -> Union[Ok[List[Lb]], Err[StorageError]]:
        result = []
        for data in self._lbs.values():
            result.append(Lb(
                lb_id=LbId(data["lb_id"]),
                name=data["name"],
                p=data["p"],
                description=data["description"],
            ))
        return Ok(result)

    # --- Transactions ---

    def txn_insert(
        self, txn: TransactionInput
    ) -> Union[Ok[Transaction], Err[StorageError]]:
        cnt = CntId(self._next_cnt())
        row = {
            "cnt": int(cnt), "act": int(txn.act), "dt": txn.dt,
            "src": int(txn.src), "lb": int(txn.lb), "id": int(txn.id),
            "val": int(txn.val),
            "p": txn.p,
        }
        self._transactions.append(row)
        return Ok(Transaction(
            cnt=cnt, act=txn.act, dt=txn.dt,
            src=txn.src, lb=txn.lb, id=txn.id,
            p=txn.p, val=txn.val,
        ))

    def txn_query(
        self,
        src_id: Optional[SrcId] = None,
        lb_id: Optional[LbId] = None,
        id_id: Optional[IdId] = None,
        until_dt: Optional[float] = None,
        from_cnt: Optional[CntId] = None,
        include_archive: bool = False,
    ) -> Union[Ok[List[Transaction]], Err[StorageError]]:
        pool = self._transactions + (self._archive if include_archive else [])
        result = []
        for row in sorted(pool, key=lambda r: r["cnt"]):
            if src_id is not None and row["src"] != int(src_id):
                continue
            if lb_id is not None and row["lb"] != int(lb_id):
                continue
            if id_id is not None and row["id"] != int(id_id):
                continue
            if until_dt is not None and row["dt"] > until_dt:
                continue
            if from_cnt is not None and row["cnt"] <= int(from_cnt):
                continue
            result.append(Transaction(
                cnt=CntId(row["cnt"]), act=ActId(row["act"]), dt=row["dt"],
                src=SrcId(row["src"]), lb=LbId(row["lb"]), id=IdId(row["id"]),
                p=row["p"], val=ValId(row["val"]),
            ))
        return Ok(result)

    def txn_archive(self, until_dt: float) -> Union[Ok[int], Err[StorageError]]:
        to_move = [r for r in self._transactions if r["dt"] <= until_dt]
        self._archive.extend(to_move)
        self._transactions = [r for r in self._transactions if r["dt"] > until_dt]
        return Ok(len(to_move))

    def txn_delete(
        self,
        src_id: SrcId,
        lb_id: Optional[LbId] = None,
    ) -> Union[Ok[int], Err[StorageError]]:
        def matches(row: Dict) -> bool:
            if row["src"] != int(src_id):
                return False
            if lb_id is not None and row["lb"] != int(lb_id):
                return False
            return True

        before = len(self._transactions)
        self._transactions = [r for r in self._transactions if not matches(r)]
        self._archive = [r for r in self._archive if not matches(r)]
        return Ok(before - len(self._transactions))

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

