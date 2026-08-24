from __future__ import annotations

from datetime import datetime
import json
from typing import Any
from uuid import uuid4

from .database import connect, create_database_backup, init_db
from .explainability import SEVERE_CODES, _base_score, _triggers
from .governance import connect as governance_connect, list_governance
from .tenancy import ACTIVE_DATABASE, product_database

POLICIES = {"rigid": "rigid-1.0", "hybrid": "hybrid-1.0"}


def _classification(score: float) -> str:
    if score == 100: return "Extraordinário"
    if score >= 85: return "Supera as expectativas"
    if score >= 70: return "Atende as expectativas"
    if score >= 50: return "Pode Melhorar"
    return "Pode Melhorar Muito"


def scores_for(analysis: dict[str, Any]) -> tuple[float, float]:
    base = _base_score(analysis)
    triggers = _triggers(analysis)
    rigid = 0.0 if triggers else base
    hybrid = 0.0 if any(item["code"] in SEVERE_CODES for item in triggers) else base
    return rigid, hybrid


def policy_state() -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT * FROM scoring_policy_state WHERE id=1").fetchone()
    return dict(row) if row else {"id": 1, "policy": "rigid", "version": POLICIES["rigid"],
                                  "activated_by": None, "activated_at": None, "operation_id": None}


def apply_active_policy_to_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    state = policy_state()
    rigid, hybrid = scores_for(analysis)
    score = hybrid if state["policy"] == "hybrid" else rigid
    analysis["score_operador"] = score
    analysis["classificacao_operador"] = _classification(score)
    analysis["scoring_policy"] = {"policy": state["policy"], "version": state["version"],
                                  "rigid_score": rigid, "hybrid_score": hybrid,
                                  "applied_at": datetime.now().isoformat()}
    return analysis


def preview_active_database() -> dict[str, Any]:
    state = policy_state()
    with connect() as db:
        rows = [json.loads(row[0]) for row in db.execute("SELECT analysis_json FROM interactions")]
    rigid_scores, hybrid_scores = zip(*(scores_for(row) for row in rows)) if rows else ((), ())
    return {"active_policy": state["policy"], "version": state["version"], "total": len(rows),
            "rigid": {"zeros": sum(score == 0 for score in rigid_scores),
                      "average": round(sum(rigid_scores) / len(rows), 1) if rows else 0},
            "hybrid": {"zeros": sum(score == 0 for score in hybrid_scores),
                       "average": round(sum(hybrid_scores) / len(rows), 1) if rows else 0},
            "changed_if_hybrid": sum(a != b for a, b in zip(rigid_scores, hybrid_scores))}


def _audit_governance(actor_id: int, operation_id: str, policy: str, slugs: list[str], results: list[dict]) -> None:
    with governance_connect() as db:
        db.execute("INSERT INTO access_audit(user_id,action,target,details_json) VALUES(?,?,?,?)",
                   (actor_id, "SCORING_POLICY_APPLIED", operation_id,
                    json.dumps({"policy": policy, "products": slugs, "results": results}, ensure_ascii=False)))


def preview_products(slugs: list[str]) -> list[dict[str, Any]]:
    products = {item["slug"]: item for item in list_governance()["products"] if item["active"]}
    invalid = sorted(set(slugs) - products.keys())
    if invalid: raise ValueError("Produto(s) inválido(s): " + ", ".join(invalid))
    result = []
    for slug in dict.fromkeys(slugs):
        token = ACTIVE_DATABASE.set(product_database(slug))
        try: result.append({"slug": slug, "name": products[slug]["name"], **preview_active_database()})
        finally: ACTIVE_DATABASE.reset(token)
    return result


def apply_policy_products(slugs: list[str], policy: str, actor_id: int) -> dict[str, Any]:
    if policy not in POLICIES: raise ValueError("Política inválida")
    products = {item["slug"]: item for item in list_governance()["products"] if item["active"]}
    invalid = sorted(set(slugs) - products.keys())
    if not slugs: raise ValueError("Selecione ao menos um produto")
    if invalid: raise ValueError("Produto(s) inválido(s): " + ", ".join(invalid))
    operation_id = str(uuid4()); results = []
    for slug in dict.fromkeys(slugs):
        token = ACTIVE_DATABASE.set(product_database(slug))
        try:
            init_db(); backup = create_database_backup(f"before_policy_{policy}")
            previous = policy_state()["policy"]; changed = 0
            with connect() as db:
                rows = [dict(row) for row in db.execute("SELECT id,score_operator,analysis_json FROM interactions")]
                for row in rows:
                    analysis = json.loads(row["analysis_json"]); rigid, hybrid = scores_for(analysis)
                    target = hybrid if policy == "hybrid" else rigid
                    prior = float(row["score_operator"] or 0)
                    analysis["score_operador"] = target
                    analysis["classificacao_operador"] = _classification(target)
                    analysis["scoring_policy"] = {"policy": policy, "version": POLICIES[policy],
                                                  "rigid_score": rigid, "hybrid_score": hybrid,
                                                  "operation_id": operation_id, "applied_at": datetime.now().isoformat()}
                    db.execute("UPDATE interactions SET score_operator=?,analysis_json=? WHERE id=?",
                               (target, json.dumps(analysis, ensure_ascii=False), row["id"]))
                    if prior != target:
                        changed += 1
                        db.execute("""INSERT INTO scoring_policy_history(interaction_id,previous_score,new_score,
                                   previous_policy,new_policy,policy_version,actor_id,operation_id)
                                   VALUES(?,?,?,?,?,?,?,?)""",
                                   (row["id"], prior, target, previous, policy, POLICIES[policy], actor_id, operation_id))
                db.execute("""INSERT INTO scoring_policy_state(id,policy,version,activated_by,activated_at,operation_id)
                           VALUES(1,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET policy=excluded.policy,
                           version=excluded.version,activated_by=excluded.activated_by,
                           activated_at=excluded.activated_at,operation_id=excluded.operation_id""",
                           (policy, POLICIES[policy], actor_id, datetime.now().isoformat(), operation_id))
            results.append({"slug": slug, "name": products[slug]["name"], "previous_policy": previous,
                            "policy": policy, "changed": changed, "backup": backup["filename"]})
        finally: ACTIVE_DATABASE.reset(token)
    _audit_governance(actor_id, operation_id, policy, slugs, results)
    return {"operation_id": operation_id, "policy": policy, "version": POLICIES[policy], "products": results}
