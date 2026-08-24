from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from .config import BASE_DIR, DATA_DIR, DATABASE_PATH
from .parser import parse_transcript
from .tenancy import active_database

DATABASE_BACKUP_DIR = BASE_DIR / "backups" / "database"

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS analysis_batches (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 total_files INTEGER DEFAULT 0, processed_files INTEGER DEFAULT 0, failed_files INTEGER DEFAULT 0, skipped_files INTEGER DEFAULT 0,
 uploaded_by TEXT
);
CREATE TABLE IF NOT EXISTS interactions (
 id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES analysis_batches(id), filename TEXT NOT NULL,
 content_hash TEXT NOT NULL, analysis_status TEXT NOT NULL, score_operator REAL, score_experience REAL,
 product TEXT, motive TEXT, analysis_json TEXT NOT NULL, source_type TEXT DEFAULT 'txt',
 source_filename TEXT, source_sheet TEXT, source_row INTEGER, metadata_json TEXT DEFAULT '{}', fingerprint TEXT,
 analysis_date TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(batch_id, content_hash)
);
CREATE TABLE IF NOT EXISTS transcript_turns (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL REFERENCES interactions(id), turn_number INTEGER,
 speaker TEXT, text_original TEXT, text_normalized TEXT, char_start INTEGER, char_end INTEGER
);
CREATE TABLE IF NOT EXISTS evidences (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL REFERENCES interactions(id), turn_number INTEGER,
 regex_id TEXT, criterion_code TEXT, category TEXT, speaker TEXT, evidence_text TEXT, normalized_text TEXT,
 start_position INTEGER, end_position INTEGER, is_negated INTEGER, confidence_level TEXT
);
CREATE TABLE IF NOT EXISTS monitoring_criteria_results (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL REFERENCES interactions(id), code TEXT,
 name TEXT, group_name TEXT, weight REAL, classification TEXT, factor REAL, score REAL, justification TEXT,
 penalty REAL, bonus REAL, UNIQUE(interaction_id, code)
);
CREATE TABLE IF NOT EXISTS interaction_metadata (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL REFERENCES interactions(id),
 original_key TEXT NOT NULL, normalized_key TEXT NOT NULL, value_text TEXT,
 UNIQUE(interaction_id, original_key)
);
CREATE TABLE IF NOT EXISTS nlp_results (
 interaction_id TEXT PRIMARY KEY REFERENCES interactions(id), model_version TEXT NOT NULL,
 provider TEXT NOT NULL, confidence REAL, result_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS causal_analysis_results (
 interaction_id TEXT PRIMARY KEY REFERENCES interactions(id), model_version TEXT NOT NULL,
 mode TEXT NOT NULL DEFAULT 'shadow', confidence REAL NOT NULL DEFAULT 0, status TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS causal_analysis_reviews (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL REFERENCES interactions(id),
 decision TEXT NOT NULL, corrected_root TEXT, reviewer_id INTEGER, notes TEXT,
 model_version TEXT NOT NULL, reviewed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS scoring_policy_state (
 id INTEGER PRIMARY KEY CHECK(id=1), policy TEXT NOT NULL DEFAULT 'rigid', version TEXT NOT NULL DEFAULT 'rigid-1.0',
 activated_by INTEGER, activated_at TEXT DEFAULT CURRENT_TIMESTAMP, operation_id TEXT
);
CREATE TABLE IF NOT EXISTS scoring_policy_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, interaction_id TEXT NOT NULL, previous_score REAL NOT NULL,
 new_score REAL NOT NULL, previous_policy TEXT NOT NULL, new_policy TEXT NOT NULL, policy_version TEXT NOT NULL,
 actor_id INTEGER, operation_id TEXT NOT NULL, changed_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_interactions_batch ON interactions(batch_id);
CREATE INDEX IF NOT EXISTS ix_evidences_interaction ON evidences(interaction_id);
CREATE INDEX IF NOT EXISTS ix_interactions_product ON interactions(product);
CREATE INDEX IF NOT EXISTS ix_metadata_key_value ON interaction_metadata(normalized_key, value_text);
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(active_database() or DATABASE_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init_db() -> None:
    with connect() as db:
        db.executescript(SCHEMA)
        existing = {row["name"] for row in db.execute("PRAGMA table_info(interactions)")}
        migrations = {
            "source_type": "ALTER TABLE interactions ADD COLUMN source_type TEXT DEFAULT 'txt'",
            "source_filename": "ALTER TABLE interactions ADD COLUMN source_filename TEXT",
            "source_sheet": "ALTER TABLE interactions ADD COLUMN source_sheet TEXT",
            "source_row": "ALTER TABLE interactions ADD COLUMN source_row INTEGER",
            "metadata_json": "ALTER TABLE interactions ADD COLUMN metadata_json TEXT DEFAULT '{}'",
            "fingerprint": "ALTER TABLE interactions ADD COLUMN fingerprint TEXT",
            "analysis_date": "ALTER TABLE interactions ADD COLUMN analysis_date TEXT",
        }
        for name, sql in migrations.items():
            if name not in existing:
                db.execute(sql)
        batch_columns = {row["name"] for row in db.execute("PRAGMA table_info(analysis_batches)")}
        if "skipped_files" not in batch_columns:
            db.execute("ALTER TABLE analysis_batches ADD COLUMN skipped_files INTEGER DEFAULT 0")
        if "uploaded_by" not in batch_columns:
            db.execute("ALTER TABLE analysis_batches ADD COLUMN uploaded_by TEXT")
        db.execute("CREATE INDEX IF NOT EXISTS ix_interactions_fingerprint ON interactions(fingerprint)")
        db.execute("CREATE INDEX IF NOT EXISTS ix_interactions_analysis_date ON interactions(analysis_date)")
        missing = [dict(r) for r in db.execute("SELECT id FROM interactions WHERE fingerprint IS NULL OR fingerprint='' OR analysis_date IS NULL")]
        for row in missing:
            turns = [dict(t) for t in db.execute("SELECT speaker,text_original FROM transcript_turns WHERE interaction_id=? ORDER BY turn_number", (row["id"],))]
            canonical = "\n".join(f"{t['speaker']}:{' '.join(t['text_original'].lower().split())}" for t in turns)
            fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest() if canonical else None
            db.execute("UPDATE interactions SET fingerprint=COALESCE(fingerprint,?),analysis_date=COALESCE(analysis_date,date(created_at)) WHERE id=?", (fingerprint,row["id"]))


def create_batch(name: str, total: int, uploaded_by: str | None = None) -> str:
    batch_id = str(uuid4())
    with connect() as db:
        db.execute("INSERT INTO analysis_batches(id,name,status,total_files,uploaded_by) VALUES(?,?,?,?,?)", (batch_id,name,"PROCESSING",total,uploaded_by))
    return batch_id


def interaction_hash(filename: str, raw: str, source_filename: str | None = None,
                     source_sheet: str | None = None, source_row: int | None = None) -> str:
    turns = parse_transcript(raw)
    canonical = "\n".join(f"{turn.speaker}:{' '.join(turn.text_original.lower().split())}" for turn in turns)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def find_interaction_by_hash(content_hash: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT id,batch_id,filename,product,created_at FROM interactions WHERE fingerprint=? ORDER BY created_at DESC LIMIT 1", (content_hash,)).fetchone()
    return dict(row) if row else None


def save_interaction(batch_id: str, filename: str, raw: str, turns: Iterable, analysis: dict,
                     source_type: str = "txt", source_filename: str | None = None,
                     source_sheet: str | None = None, source_row: int | None = None,
                     metadata: dict | None = None) -> tuple[str, bool]:
    metadata = metadata or {}
    from .scoring_policy import apply_active_policy_to_analysis
    analysis = apply_active_policy_to_analysis(analysis)
    digest = interaction_hash(filename, raw, source_filename, source_sheet, source_row)
    interaction_id = str(uuid4())
    with connect() as db:
        existing = db.execute("SELECT id FROM interactions WHERE batch_id=? AND content_hash=?", (batch_id,digest)).fetchone()
        if existing:
            return existing["id"], False
        legacy_digest = hashlib.sha256(f"{source_filename or filename}|{source_sheet or ''}|{source_row or ''}|{raw}".encode("utf-8")).hexdigest()
        db.execute("INSERT INTO interactions(id,batch_id,filename,content_hash,analysis_status,score_operator,score_experience,product,motive,analysis_json,source_type,source_filename,source_sheet,source_row,metadata_json,fingerprint,analysis_date) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (interaction_id,batch_id,filename,legacy_digest,analysis["analysis_status"],analysis["score_operador"],analysis["score_experiencia"],analysis["produto_principal"],analysis["motivo_contato"],json.dumps(analysis,ensure_ascii=False),source_type,source_filename or filename,source_sheet,source_row,json.dumps(metadata,ensure_ascii=False),digest,datetime.now().date().isoformat()))
        db.executemany("INSERT INTO transcript_turns(interaction_id,turn_number,speaker,text_original,text_normalized,char_start,char_end) VALUES(?,?,?,?,?,?,?)",
            [(interaction_id,t.number,t.speaker,t.text_original,t.text_normalized,t.char_start,t.char_end) for t in turns])
        for e in analysis["evidences"]:
            codes = e.get("criteria") or [None]
            db.executemany("INSERT INTO evidences(interaction_id,turn_number,regex_id,criterion_code,category,speaker,evidence_text,normalized_text,start_position,end_position,is_negated,confidence_level) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                [(interaction_id,e["turn_number"],e["regex_id"],c,e["category"],e["speaker"],e["text"],e["normalized_text"],e["start"],e["end"],int(e["is_negated"]),e["confidence"]) for c in codes])
        db.executemany("INSERT INTO monitoring_criteria_results(interaction_id,code,name,group_name,weight,classification,factor,score,justification,penalty,bonus) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            [(interaction_id,c,r["name"],r["group"],r["weight"],r["classification"],r["factor"],r["score"],r["justification"],r["penalty"],r["bonus"]) for c,r in analysis["criteria"].items()])
        db.executemany("INSERT INTO interaction_metadata(interaction_id,original_key,normalized_key,value_text) VALUES(?,?,?,?)",
            [(interaction_id,str(k),_normalize_key(str(k)),str(v)) for k,v in metadata.items()])
        nlp = analysis.get("nlp")
        if nlp:
            db.execute("INSERT OR REPLACE INTO nlp_results(interaction_id,model_version,provider,confidence,result_json) VALUES(?,?,?,?,?)",
                (interaction_id,nlp.get("version","unknown"),nlp.get("provider","local"),nlp.get("confidence",0),json.dumps(nlp,ensure_ascii=False)))
        causal = analysis.get("causal_funnel")
        if causal:
            db.execute("INSERT OR REPLACE INTO causal_analysis_results(interaction_id,model_version,mode,confidence,status,result_json) VALUES(?,?,?,?,?,?)",
                (interaction_id,causal.get("version","unknown"),causal.get("mode","shadow"),causal.get("confidence",0),causal.get("status","Não determinada"),json.dumps(causal,ensure_ascii=False)))
    return interaction_id, True


def finish_batch(batch_id: str, processed: int, failed: int, skipped: int = 0) -> None:
    with connect() as db:
        db.execute("UPDATE analysis_batches SET status=?,processed_files=?,failed_files=?,skipped_files=? WHERE id=?", ("COMPLETED" if failed == 0 else "COMPLETED_WITH_ERRORS",processed,failed,skipped,batch_id))


def get_interaction(interaction_id: str) -> dict | None:
    with connect() as db:
        row = db.execute("SELECT * FROM interactions WHERE id=?",(interaction_id,)).fetchone()
    return json.loads(row["analysis_json"]) if row else None


def enrich_existing_nlp() -> dict:
    from .nlp_engine import analyze_nlp
    init_db(); updated, skipped = 0, 0
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT id,analysis_json FROM interactions")]
        for row in rows:
            analysis = json.loads(row["analysis_json"])
            if analysis.get("nlp"):
                skipped += 1; continue
            turns = [dict(t) for t in db.execute("SELECT speaker,text_original FROM transcript_turns WHERE interaction_id=? ORDER BY turn_number",(row["id"],))]
            text = "\n".join(f"#{t['speaker'].title()}: {t['text_original']}" for t in turns)
            nlp = analyze_nlp(text)
            analysis["nlp"] = nlp
            db.execute("UPDATE interactions SET analysis_json=? WHERE id=?",(json.dumps(analysis,ensure_ascii=False),row["id"]))
            db.execute("INSERT OR REPLACE INTO nlp_results(interaction_id,model_version,provider,confidence,result_json) VALUES(?,?,?,?,?)",
                       (row["id"],nlp["version"],nlp["provider"],nlp["confidence"],json.dumps(nlp,ensure_ascii=False)))
            updated += 1
    return {"updated":updated,"skipped":skipped}


def enrich_existing_causal() -> dict:
    from .causal_engine import analyze_causal_funnel
    init_db(); updated = 0
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT id,analysis_json FROM interactions")]
        for row in rows:
            analysis = json.loads(row["analysis_json"])
            causal = analyze_causal_funnel(analysis)
            analysis["causal_funnel"] = causal
            db.execute("UPDATE interactions SET analysis_json=? WHERE id=?", (json.dumps(analysis,ensure_ascii=False),row["id"]))
            db.execute("INSERT OR REPLACE INTO causal_analysis_results(interaction_id,model_version,mode,confidence,status,result_json) VALUES(?,?,?,?,?,?)",
                (row["id"],causal["version"],causal["mode"],causal["confidence"],causal["status"],json.dumps(causal,ensure_ascii=False)))
            updated += 1
    return {"updated":updated,"mode":"shadow"}


def enrich_existing_attendants() -> dict:
    from .products import extract_attendant_from_turns
    init_db(); updated = 0; unresolved = 0
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT id,analysis_json FROM interactions")]
        for row in rows:
            analysis = json.loads(row["analysis_json"])
            if str(analysis.get("atendente") or "").strip() not in {"", "Não identificado"}:
                continue
            turns = [dict(t) for t in db.execute("SELECT speaker,text_original FROM transcript_turns WHERE interaction_id=? ORDER BY turn_number", (row["id"],))]
            attendant, evidence = extract_attendant_from_turns(turns)
            if attendant == "Não identificado":
                unresolved += 1; continue
            analysis["atendente"] = attendant
            analysis["atendente_origem"] = "autoapresentação na transcrição"
            analysis["atendente_evidencia"] = evidence
            db.execute("UPDATE interactions SET analysis_json=? WHERE id=?", (json.dumps(analysis,ensure_ascii=False),row["id"]))
            updated += 1
    return {"updated":updated,"unresolved":unresolved,"method":"autoapresentação explícita do atendente"}


def list_batches() -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM analysis_batches ORDER BY created_at DESC")]


def batch_summary(batch_id: str) -> dict:
    with connect() as db:
        rows = [dict(r) for r in db.execute("SELECT id,filename,score_operator,score_experience,product,motive,analysis_status FROM interactions WHERE batch_id=?",(batch_id,))]
    count = len(rows)
    products: dict[str, int] = {}
    for row in rows:
        products[row["product"]] = products.get(row["product"], 0) + 1
    return {"batch_id":batch_id,"interactions":rows,"total":count,"products":products,
        "avg_score_operator":round(sum(r["score_operator"] for r in rows)/count,2) if count else 0,
        "avg_score_experience":round(sum(r["score_experience"] for r in rows)/count,2) if count else 0}


def list_products() -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT product, COUNT(*) AS interactions, ROUND(AVG(score_operator),2) AS avg_score_operator, ROUND(AVG(score_experience),2) AS avg_score_experience FROM interactions GROUP BY product ORDER BY interactions DESC, product")]


def list_interactions_by_product(product: str) -> list[dict]:
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id,filename,product,motive,score_operator,score_experience,source_type,source_filename,source_sheet,source_row FROM interactions WHERE product=? ORDER BY created_at DESC",(product,))]


def _delete_interaction_rows(db: sqlite3.Connection, interaction_ids: list[str]) -> None:
    if not interaction_ids:
        return
    placeholders = ",".join("?" for _ in interaction_ids)
    for table in ("causal_analysis_reviews", "causal_analysis_results", "nlp_results", "evidences", "transcript_turns", "monitoring_criteria_results", "interaction_metadata"):
        db.execute(f"DELETE FROM {table} WHERE interaction_id IN ({placeholders})", interaction_ids)
    db.execute(f"DELETE FROM interactions WHERE id IN ({placeholders})", interaction_ids)


def remove_interaction(interaction_id: str) -> bool:
    with connect() as db:
        row = db.execute("SELECT batch_id FROM interactions WHERE id=?", (interaction_id,)).fetchone()
        if not row:
            return False
        _delete_interaction_rows(db, [interaction_id])
        db.execute("UPDATE analysis_batches SET processed_files=MAX(0,processed_files-1) WHERE id=?", (row["batch_id"],))
    return True


def create_database_backup(reason: str = "manual") -> dict:
    init_db()
    DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe_reason = "".join(c if c.isalnum() or c in "-_" else "_" for c in reason)[:40] or "manual"
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    target = DATABASE_BACKUP_DIR / f"{(active_database() or DATABASE_PATH).stem}_{stamp}_{safe_reason}.db"
    source = connect()
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close(); source.close()
    return {"filename":target.name,"path":str(target),"size_bytes":target.stat().st_size,"created_at":datetime.now().isoformat(),"reason":reason}


def list_database_backups() -> list[dict]:
    DATABASE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return [{"filename":p.name,"size_bytes":p.stat().st_size,"created_at":datetime.fromtimestamp(p.stat().st_mtime).isoformat()} for p in sorted(DATABASE_BACKUP_DIR.glob("*.db"), key=lambda p:p.stat().st_mtime, reverse=True)]


def clear_database(product: str | None = None) -> dict:
    backup = create_database_backup("before_clear_" + (product or "all"))
    with connect() as db:
        if product:
            rows = [dict(r) for r in db.execute("SELECT id,batch_id FROM interactions WHERE product=?", (product,))]
            _delete_interaction_rows(db, [r["id"] for r in rows])
            for batch_id in {r["batch_id"] for r in rows}:
                count = db.execute("SELECT COUNT(*) FROM interactions WHERE batch_id=?", (batch_id,)).fetchone()[0]
                db.execute("UPDATE analysis_batches SET processed_files=? WHERE id=?", (count,batch_id))
        else:
            count = db.execute("SELECT COUNT(*) FROM interactions").fetchone()[0]
            ids = [r[0] for r in db.execute("SELECT id FROM interactions")]
            _delete_interaction_rows(db, ids)
            db.execute("DELETE FROM analysis_batches")
            return {"deleted":count,"scope":"all","backup":backup}
    return {"deleted":len(rows),"scope":product,"backup":backup}


def list_periods() -> dict:
    with connect() as db:
        years = [r[0] for r in db.execute("SELECT DISTINCT CAST(substr(analysis_date,1,4) AS INTEGER) FROM interactions ORDER BY 1 DESC")]
        months = [dict(r) for r in db.execute("SELECT substr(analysis_date,1,4) AS year, substr(analysis_date,6,2) AS month, COUNT(*) AS interactions FROM interactions GROUP BY 1,2 ORDER BY 1 DESC,2 DESC")]
        days = [dict(r) for r in db.execute("SELECT analysis_date AS day, COUNT(*) AS interactions FROM interactions GROUP BY 1 ORDER BY 1 DESC")]
    return {"years":years,"months":months,"days":days}


def history(year: int | None = None, month: int | None = None, day: str | None = None, product: str | None = None) -> list[dict]:
    where, params = [], []
    if year: where.append("substr(analysis_date,1,4)=?"); params.append(f"{year:04d}")
    if month: where.append("substr(analysis_date,6,2)=?"); params.append(f"{month:02d}")
    if day: where.append("analysis_date=?"); params.append(day)
    if product: where.append("product=?"); params.append(product)
    sql = "SELECT id,filename,product,motive,score_operator,score_experience,analysis_date,created_at FROM interactions"
    if where: sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC"
    with connect() as db:
        return [dict(r) for r in db.execute(sql,params)]


def _normalize_key(value: str) -> str:
    import re, unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFD", value.lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
