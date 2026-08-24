from __future__ import annotations

from collections import Counter
import json
from statistics import median
from typing import Any

from .database import connect


CRITERIA_POLICY = {
    "at_inad_compr1": {"label": "Direcionamento para pesquisa", "kind": "absence", "hybrid": "Alerta/dedução"},
    "at_inad_compr2": {"label": "Omissão do protocolo", "kind": "absence", "hybrid": "Validar texto + metadado"},
    "at_inad_compr3": {"label": "Falta de informação sobre prazo", "kind": "absence", "hybrid": "Alerta/dedução"},
    "at_inad_compr4": {"label": "Alteração de prazo", "kind": "explicit", "hybrid": "Mantém zeramento"},
    "at_inad_compr5": {"label": "Desligamento inadequado", "kind": "absence", "hybrid": "Alerta/dedução"},
    "at_inad_compr6": {"label": "Linguagem ofensiva", "kind": "explicit", "hybrid": "Mantém zeramento"},
    "at_inad_compr7": {"label": "Causar prejuízo", "kind": "explicit", "hybrid": "Mantém zeramento"},
}
SEVERE_CODES = {code for code, policy in CRITERIA_POLICY.items() if policy["kind"] == "explicit"}


def _base_score(analysis: dict[str, Any]) -> float:
    criteria = analysis.get("criteria", {})
    base = sum(float(item.get("score") or 0) for item in criteria.values()
               if item.get("group") in {"relationship", "resolution", "cx"})
    bonus = float(criteria.get("inv_extra1", {}).get("bonus") or 0)
    return round(min(100, base + bonus), 2)


def _triggers(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for code, criterion in analysis.get("criteria", {}).items():
        if criterion.get("group") != "noncompliance" or criterion.get("classification") != "Sim":
            continue
        policy = CRITERIA_POLICY.get(code, {"label": criterion.get("name", code), "kind": "unknown", "hybrid": "Revisão humana"})
        evidence = criterion.get("evidence") or []
        result.append({
            "code": code,
            "name": criterion.get("name") or policy["label"],
            "kind": policy["kind"],
            "basis": "Evidência Regex explícita" if evidence else "Ausência do padrão Regex esperado",
            "evidence": evidence[:5],
            "justification": criterion.get("justification", ""),
            "current_effect": "Zera atendimento",
            "hybrid_effect": policy["hybrid"],
        })
    return result


def _band(score: float) -> str:
    if score == 0: return "0"
    if score < 50: return "1–49"
    if score < 70: return "50–69"
    if score < 85: return "70–84"
    if score < 100: return "85–99"
    return "100"


def explainability_dashboard(criterion: str | None = None, status: str | None = None,
                             search: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    with connect() as db:
        rows = [dict(row) for row in db.execute(
            """SELECT id,filename,product,analysis_date,metadata_json,analysis_json
               FROM interactions ORDER BY created_at DESC""")]
        state_row = db.execute("SELECT policy,version FROM scoring_policy_state WHERE id=1").fetchone()
    active_policy = dict(state_row) if state_row else {"policy":"rigid","version":"rigid-1.0"}

    analyses, criterion_counts = [], Counter()
    for row in rows:
        analysis = json.loads(row.pop("analysis_json"))
        metadata = json.loads(row.pop("metadata_json") or "{}")
        triggers = _triggers(analysis)
        for trigger in triggers:
            criterion_counts[trigger["code"]] += 1
        severe = any(trigger["code"] in SEVERE_CODES for trigger in triggers)
        simulated = 0.0 if severe else _base_score(analysis)
        nlp = analysis.get("nlp") or {}
        protocol_in_metadata = any("protocolo" in str(key).lower() and str(value).strip()
                                   for key, value in metadata.items())
        item = {
            **row,
            "operator": str(analysis.get("atendente") or "Não identificado"),
            "official_score": float(analysis.get("score_operador") or 0),
            "simulated_score": simulated,
            "official_zero": float(analysis.get("score_operador") or 0) == 0,
            "hybrid_zero": simulated == 0,
            "triggers": triggers,
            "protocol_in_metadata": protocol_in_metadata,
            "nlp": {
                "available": bool(nlp), "role": "Complementar; não decide a inaderência",
                "topic": nlp.get("primary_topic", "Não processado"),
                "sentiment": (nlp.get("sentiment") or {}).get("label", "N/D"),
                "confidence": float(nlp.get("confidence") or 0),
                "abstained": bool((nlp.get("audit") or {}).get("abstained")),
                "version": nlp.get("version", "N/D"),
            },
        }
        analyses.append(item)

    official_scores = [item["official_score"] for item in analyses]
    simulated_scores = [item["simulated_score"] for item in analyses]
    total = len(analyses)
    official_zeros = sum(item["official_zero"] for item in analyses)
    hybrid_zeros = sum(item["hybrid_zero"] for item in analyses)

    filtered = analyses
    if criterion:
        filtered = [item for item in filtered if any(t["code"] == criterion for t in item["triggers"])]
    if status == "official_zero": filtered = [item for item in filtered if item["official_zero"]]
    if status == "released_by_hybrid": filtered = [item for item in filtered if item["official_zero"] and not item["hybrid_zero"]]
    if status == "hybrid_zero": filtered = [item for item in filtered if item["hybrid_zero"]]
    if search:
        needle = search.casefold()
        filtered = [item for item in filtered if needle in f"{item['filename']} {item['operator']} {item['product']}".casefold()]

    criteria = []
    for code, policy in CRITERIA_POLICY.items():
        count = criterion_counts[code]
        criteria.append({"code": code, **policy, "count": count,
                         "share": round(count * 100 / total, 1) if total else 0,
                         "current": "Regex/regra determinística"})
    criteria.sort(key=lambda item: -item["count"])

    return {
        "methodology": {
            "official_engine": "Regex + regras determinísticas",
            "nlp_role": "Contexto complementar em modo shadow; sem autoridade sobre a nota",
            "simulation": "Ausências deixam de zerar; evidências explícitas graves mantêm zeramento",
            "writes_database": False, "active_policy":active_policy["policy"],
            "active_version":active_policy["version"],
        },
        "summary": {
            "total": total,
            "nlp_processed": sum(item["nlp"]["available"] for item in analyses),
            "official": {"average": round(sum(official_scores) / total, 1) if total else 0,
                         "median": round(median(official_scores), 1) if total else 0,
                         "zeros": official_zeros, "zero_share": round(official_zeros * 100 / total, 1) if total else 0},
            "simulated": {"average": round(sum(simulated_scores) / total, 1) if total else 0,
                          "median": round(median(simulated_scores), 1) if total else 0,
                          "zeros": hybrid_zeros, "zero_share": round(hybrid_zeros * 100 / total, 1) if total else 0},
            "released_by_hybrid": sum(item["official_zero"] and not item["hybrid_zero"] for item in analyses),
        },
        "distributions": {
            "official": dict(Counter(_band(score) for score in official_scores)),
            "simulated": dict(Counter(_band(score) for score in simulated_scores)),
        },
        "criteria": criteria,
        "filters": {"criterion": criterion, "status": status, "search": search},
        "result_count": len(filtered),
        "pagination": {"offset":max(0,offset),"limit":max(1,min(limit,200)),
                       "has_previous":offset>0,"has_next":offset+limit<len(filtered)},
        "interactions": filtered[max(0,offset):max(0,offset)+max(1,min(limit,200))],
    }
