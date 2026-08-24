from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import unicodedata

from .config import DATA_DIR, DATABASE_PATH
from .tenancy import ACTIVE_DATABASE, product_database

MARKER = DATA_DIR / "migrations" / "legacy_to_product_databases_v1.done"
ATTENDANT_ENRICHMENT_VERSION = "data-2026-08-attendant-self-presentation-v1"


def _plain(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(value).lower()) if unicodedata.category(c)!="Mn")


def classify_legacy_product(value: str) -> str:
    text=_plain(value)
    if "consignado" in text: return "consignado"
    if "seguro" in text: return "seguros"
    if "credito" in text or "central" in text or text.strip()=="cartao": return "cartao"
    if "veicul" in text: return "veiculos"
    if "invest" in text: return "investe"
    if "retenc" in text or "cip" in text: return "retencao_cip"
    return "legado_nao_classificado"


def _insert_row(db:sqlite3.Connection,table:str,row:sqlite3.Row,drop_id:bool=False) -> None:
    data=dict(row)
    if drop_id: data.pop("id",None)
    cols=list(data);db.execute(f"INSERT OR IGNORE INTO {table}({','.join(cols)}) VALUES({','.join('?' for _ in cols)})",[data[c] for c in cols])


def migrate_legacy_database() -> dict:
    if MARKER.exists() or not DATABASE_PATH.exists(): return {"status":"skipped"}
    from .database import init_db
    migrated={}
    with sqlite3.connect(DATABASE_PATH) as source:
        source.row_factory=sqlite3.Row
        interactions=list(source.execute("SELECT * FROM interactions"))
        for interaction in interactions:
            slug=classify_legacy_product(interaction["product"]);target=product_database(slug);token=ACTIVE_DATABASE.set(target)
            try:init_db()
            finally:ACTIVE_DATABASE.reset(token)
            with sqlite3.connect(target) as dest:
                batch=source.execute("SELECT * FROM analysis_batches WHERE id=?",(interaction["batch_id"],)).fetchone()
                if batch:_insert_row(dest,"analysis_batches",batch)
                _insert_row(dest,"interactions",interaction)
                for table in ("transcript_turns","evidences","monitoring_criteria_results","interaction_metadata"):
                    for row in source.execute(f"SELECT * FROM {table} WHERE interaction_id=?",(interaction["id"],)):_insert_row(dest,table,row,True)
                nlp=source.execute("SELECT * FROM nlp_results WHERE interaction_id=?",(interaction["id"],)).fetchone()
                if nlp:_insert_row(dest,"nlp_results",nlp)
            migrated[slug]=migrated.get(slug,0)+1
    for slug in migrated:
        with sqlite3.connect(product_database(slug)) as db:
            db.execute("UPDATE analysis_batches SET processed_files=(SELECT COUNT(*) FROM interactions i WHERE i.batch_id=analysis_batches.id),total_files=(SELECT COUNT(*) FROM interactions i WHERE i.batch_id=analysis_batches.id)")
    MARKER.parent.mkdir(parents=True,exist_ok=True);MARKER.write_text(json.dumps(migrated,ensure_ascii=False),encoding="utf-8")
    return {"status":"completed","migrated":migrated}


def run_product_data_migrations() -> dict:
    """Executa migrações de conteúdo uma vez no banco de produto ativo."""
    from .database import connect, create_database_backup, enrich_existing_attendants, init_db
    init_db()
    with connect() as db:
        applied = db.execute("SELECT 1 FROM data_migrations WHERE version=?", (ATTENDANT_ENRICHMENT_VERSION,)).fetchone()
        pending = db.execute("SELECT COUNT(*) FROM interactions WHERE json_extract(analysis_json,'$.atendente') IS NULL OR json_extract(analysis_json,'$.atendente') IN ('','Não identificado')").fetchone()[0]
    if applied:
        return {"version":ATTENDANT_ENRICHMENT_VERSION,"status":"already_applied"}
    backup = create_database_backup("auto_before_" + ATTENDANT_ENRICHMENT_VERSION) if pending else None
    result = enrich_existing_attendants() if pending else {"updated":0,"unresolved":0,"method":"sem dados pendentes"}
    audit = {**result,"pending_before":pending,"backup":backup["filename"] if backup else None}
    with connect() as db:
        db.execute("INSERT INTO data_migrations(version,description,result_json) VALUES(?,?,?)",
                   (ATTENDANT_ENRICHMENT_VERSION,"Extrai operador de autoapresentação explícita",json.dumps(audit,ensure_ascii=False)))
    return {"version":ATTENDANT_ENRICHMENT_VERSION,"status":"applied",**audit}
