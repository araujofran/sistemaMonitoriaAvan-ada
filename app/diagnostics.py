from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import platform
import sqlite3
import sys
import traceback
from uuid import uuid4

from .config import BASE_DIR, DATA_DIR, DATABASE_PATH
from .tenancy import active_database

DIAGNOSTICS_DIR = DATA_DIR / "diagnostics"
ERROR_LOG = DIAGNOSTICS_DIR / "errors.jsonl"
MAX_ERRORS = 100


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_error(method: str, path: str, exc: Exception) -> str:
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    error_id = uuid4().hex[:12]
    item = {"id": error_id, "timestamp": _now(), "method": method, "path": path,
            "type": type(exc).__name__, "message": str(exc),
            "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-12000:]}
    with ERROR_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    return error_id


def recent_errors(limit: int = 30) -> list[dict]:
    if not ERROR_LOG.exists(): return []
    result = []
    for line in reversed(ERROR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-MAX_ERRORS:]):
        try: result.append(json.loads(line))
        except json.JSONDecodeError: pass
        if len(result) >= max(1, min(limit, 100)): break
    return result


def system_diagnostics() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    database_path = active_database() or DATABASE_PATH
    status, counts, integrity, size = "ausente", {}, "não executado", 0
    try:
        if database_path.exists():
            size = database_path.stat().st_size
            with sqlite3.connect(database_path) as db:
                integrity = db.execute("PRAGMA quick_check").fetchone()[0]
                for table in ("analysis_batches", "interactions", "transcript_turns", "evidences", "monitoring_criteria_results", "nlp_results", "causal_analysis_results", "causal_analysis_reviews"):
                    counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "ok"
    except Exception as exc:
        status, integrity = "erro", str(exc)
    return {"generated_at": _now(),
            "application": {"base_dir": str(BASE_DIR), "python": sys.version.split()[0], "platform": platform.platform(), "pid": os.getpid()},
            "database": {"status": status, "path": str(database_path), "size_bytes": size, "integrity": integrity, "counts": counts},
            "storage": {"data_dir": str(DATA_DIR), "writable": os.access(DATA_DIR, os.W_OK)},
            "errors": {"count_visible": len(recent_errors(100)), "latest": recent_errors(10)}}
