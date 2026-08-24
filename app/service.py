from __future__ import annotations

from pathlib import Path
from .contract_validator import validate_analysis
from .database import (create_batch, create_database_backup, find_interaction_by_hash,
    finish_batch, init_db, interaction_hash, remove_interaction, save_interaction)
from .evidence_engine import collect_evidence
from .parser import parse_transcript
from .rule_engine import evaluate
from .importers import SourceRecord, load_sources
from .products import infer_attendant, infer_product, normalize_key
from .journey import interaction_path
from .nlp_engine import analyze_nlp
from .causal_engine import analyze_causal_funnel


def analyze_text(text: str, filename: str = "transcricao.txt", metadata: dict | None = None) -> tuple[list, dict]:
    turns = parse_transcript(text)
    analysis = evaluate(turns, collect_evidence(turns), filename)
    metadata = metadata or {}
    product, product_source = infer_product(metadata, text, analysis["produto_principal"])
    attendant, attendant_source = infer_attendant(metadata, analysis["atendente"])
    normalized = {normalize_key(k): v for k, v in metadata.items()}
    analysis["produto_principal"] = product
    analysis["produto_origem"] = product_source
    analysis["atendente"] = attendant
    analysis["atendente_origem"] = attendant_source
    analysis["source_metadata"] = metadata
    for target, aliases in {
        "protocolo": ("protocolo", "codigo_final", "codigo"),
        "cpf": ("cpf_format", "cpf"),
    }.items():
        value = next((normalized[a] for a in aliases if a in normalized and normalized[a] not in (None,"")), None)
        if value is not None:
            analysis[target] = str(value)
    analysis["nlp"] = analyze_nlp(text, turns)
    analysis["causal_funnel"] = analyze_causal_funnel(analysis)
    analysis["journey"] = interaction_path(analysis)
    validate_analysis(analysis)
    return turns, analysis


def preflight_paths(paths: list[Path]) -> dict:
    init_db()
    records, import_errors = load_sources(paths)
    duplicates, new_records, seen = [], 0, {}
    for record in records:
        digest = interaction_hash(record.display_filename, record.text, record.source_filename, record.sheet_name, record.source_row)
        existing = find_interaction_by_hash(digest)
        if existing:
            duplicates.append({"filename":record.display_filename,"existing":existing})
        elif digest in seen:
            duplicates.append({"filename":record.display_filename,"existing":{"id":None,"filename":seen[digest],"product":"Não processado","created_at":"repetido no próprio upload"}})
        else:
            new_records += 1; seen[digest] = record.display_filename
    return {"records":len(records),"new":new_records,"duplicates":duplicates,"duplicate_count":len(duplicates),"errors":import_errors}


def process_paths(paths: list[Path], batch_name: str = "Lote", reanalyze: bool = False) -> dict:
    init_db()
    records, import_errors = load_sources(paths)
    batch_id = create_batch(batch_name, len(records) + len(import_errors))
    processed, failed, skipped, overwritten, items = 0, len(import_errors), 0, 0, list(import_errors)
    existing_by_hash = {}
    for record in records:
        digest = interaction_hash(record.display_filename, record.text, record.source_filename, record.sheet_name, record.source_row)
        existing_by_hash[digest] = find_interaction_by_hash(digest)
    if reanalyze and any(existing_by_hash.values()):
        create_database_backup("before_reanalysis")
    seen_in_upload: set[str] = set()
    for record in records:
        try:
            digest = interaction_hash(record.display_filename, record.text, record.source_filename, record.sheet_name, record.source_row)
            if digest in seen_in_upload:
                skipped += 1
                items.append({"filename":record.display_filename,"created":False,"status":"SKIPPED_DUPLICATE_IN_UPLOAD"})
                continue
            seen_in_upload.add(digest)
            existing = existing_by_hash.get(digest)
            if existing and not reanalyze:
                skipped += 1
                items.append({"id":existing["id"],"filename":record.display_filename,"created":False,"status":"SKIPPED_ALREADY_ANALYZED","product":existing["product"]})
                continue
            if existing and reanalyze:
                remove_interaction(existing["id"]); overwritten += 1
            turns, analysis = analyze_text(record.text, record.display_filename, record.metadata)
            analysis["source"] = {"type":record.source_type,"filename":record.source_filename,"sheet":record.sheet_name,"row":record.source_row}
            interaction_id, created = save_interaction(batch_id, record.display_filename, record.text, turns, analysis,
                record.source_type, record.source_filename, record.sheet_name, record.source_row, record.metadata)
            processed += int(created)
            items.append({"id":interaction_id,"filename":record.display_filename,"created":created,"status":analysis["analysis_status"],"product":analysis["produto_principal"]})
        except Exception as exc:
            failed += 1
            items.append({"filename":record.display_filename,"error":str(exc)})
    finish_batch(batch_id, processed, failed, skipped)
    return {"batch_id":batch_id,"processed":processed,"failed":failed,"skipped":skipped,"overwritten":overwritten,"items":items}
