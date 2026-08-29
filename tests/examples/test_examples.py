"""Runs every examples/<name>/run.sh and checks its output against
examples/<name>/expected/.

Two artefacts are compared per example:
  * stdout.txt  -- verbatim stdout of run.sh (CLI messages)
  * journal.txt -- human-readable dump of the transactions journal, with the
                   non-deterministic ``created_at`` column dropped.

Regenerate the expected files after an intentional change:

    UPDATE_EXAMPLES=1 python -m pytest tests/examples/ -q
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EXAMPLES = REPO / "examples"

_JOURNAL_QUERY = """
SELECT
  t.cnt,
  a.name  AS act,
  t.dt    AS dt,
  s.name  AS src,
  l.name  AS lb,
  i.value AS id,
  COALESCE(v.value, '<null>') AS val
FROM transactions t
JOIN acts a ON a.act_id = t.act
JOIN srcs s ON s.src_id = t.src
JOIN lbs  l ON l.lb_id  = t.lb
JOIN ids  i ON i.id_id  = t.id
LEFT JOIN vals v ON v.val_id = t.val
ORDER BY t.cnt;
"""


def _example_dirs() -> list[Path]:
    return sorted(p for p in EXAMPLES.iterdir() if (p / "run.sh").is_file())


def _dump_journal(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(_JOURNAL_QUERY).fetchall()
    finally:
        conn.close()
    header = "cnt | act | dt | src | lb | id | val"
    lines = [header, "-" * len(header)]
    for r in rows:
        lines.append(" | ".join(str(c) for c in r))
    return "\n".join(lines) + "\n"


def _run(example: Path, workdir: Path) -> str:
    proc = subprocess.run(
        ["bash", str(example / "run.sh"), str(workdir)],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"{example.name}/run.sh exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc.stdout


def _check(path: Path, actual: str) -> None:
    if os.environ.get("UPDATE_EXAMPLES"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        return
    assert path.is_file(), f"missing expected file: {path} (run with UPDATE_EXAMPLES=1)"
    assert actual == path.read_text(encoding="utf-8"), f"mismatch vs {path}"


@pytest.mark.parametrize("example", _example_dirs(), ids=lambda p: p.name)
def test_example(example: Path, tmp_path: Path) -> None:
    stdout = _run(example, tmp_path)
    _check(example / "expected" / "stdout.txt", stdout)
    _check(example / "expected" / "journal.txt", _dump_journal(tmp_path / "data.db"))


if __name__ == "__main__":  # allow: python tests/examples/test_examples.py
    sys.exit(pytest.main([__file__, "-q"]))
