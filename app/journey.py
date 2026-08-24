from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

from .database import connect
from .causal_engine import analyze_causal_funnel

UNKNOWN_MARKERS = ("nao identific", "não identific", "nao aplic", "não aplic", "evidencia tecnica insuficiente", "evid�ncia t�cnica insuficiente")
GENERIC_ROOT_MARKERS = ("nao permite determinar", "não permite determinar", "n�o permite determinar")


def _plain(value: Any) -> str:
    import unicodedata
    text = "" if value is None else str(value)
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _usable(value: Any) -> bool:
    text = _plain(value).strip()
    return bool(text) and not any(marker in text for marker in UNKNOWN_MARKERS)


def _metadata_value(analysis: dict, *names: str) -> str | None:
    metadata = analysis.get("source_metadata", {})
    normalized = {re.sub(r"[^a-z0-9]+", "_", _plain(k)).strip("_"): v for k, v in metadata.items()}
    return next((str(normalized[name]) for name in names if name in normalized and _usable(normalized[name])), None)


def _presented_category(analysis: dict) -> str:
    # SENTIMENTO_CLIENTE frequently contains ordinal codes (1..5), not a
    # business cause. Causal presentation must prefer textual category fields.
    for name in ("categoria_1", "categoria"):
        value = _metadata_value(analysis, name)
        if value and not re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", value.strip()):
            return value
    return str(analysis.get("motivo_contato") or "Não identificado")


def extract_customer_voice(analysis: dict) -> str:
    candidates = []
    for evidence in analysis.get("evidences", []):
        if evidence.get("speaker") == "CLIENTE" and not evidence.get("is_negated"):
            text = str(evidence.get("text", "")).strip()
            if len(text) >= 4:
                priority = 3 if evidence.get("category") in {"intent", "friction", "risk"} else 1
                candidates.append((priority, len(text), text))
    root_evidence = analysis.get("root_cause", {}).get("causaraiz4_evidencia", [])
    if isinstance(root_evidence, list):
        candidates.extend((2, len(str(text)), str(text)) for text in root_evidence if _usable(text))
    if _usable(analysis.get("principal_insatisfacao")):
        text = str(analysis["principal_insatisfacao"])
        candidates.append((4, len(text), text))
    return max(candidates, default=(0, 0, "Sem fala causal suficiente"))[2][:240]


def interaction_path(analysis: dict) -> dict[str, Any]:
    causal = analysis.get("causal_funnel") or analyze_causal_funnel(analysis)
    root = analysis.get("root_cause", {})
    voice = extract_customer_voice(analysis)
    presented = _presented_category(analysis)
    motivating = analysis.get("principal_insatisfacao")
    if not _usable(motivating):
        motivating = root.get("causaraiz1_descricao") or analysis.get("motivo_contato") or "Não identificado"
    friction = root.get("causaraiz3_dono_jornada")
    if not _usable(friction):
        friction = "Fricção não categorizada" if analysis.get("cx1_friccao", {}).get("classificacao") == "Sim" else "Sem fricção comprovada"
    responsibility = analysis.get("responsabilidade") or "Não identificado"
    root_reason = root.get("causaraiz2_motivo")
    generic = not _usable(root_reason) or any(marker in _plain(root_reason) for marker in GENERIC_ROOT_MARKERS)
    root_cause = str(causal["root_candidate"]) if causal.get("status") != "Não determinada" else (f"{friction} — mecanismo técnico não determinado" if generic else str(root_reason))
    return {
        "voice": str(voice), "presented": str(presented), "motivating": str(motivating),
        "friction": str(friction), "responsibility": str(responsibility), "root": root_cause,
        "root_confidence": str(causal.get("status") or ("Categorial" if generic else "Com evidência específica")),
        "causal_confidence": float(causal.get("confidence") or 0),
        "journey_stage": str(causal.get("journey_stage") or "Não determinada"),
        "causal_evidence": causal.get("evidence") or [],
    }


def _top(counter: Counter, limit: int = 8) -> list[dict]:
    total = sum(counter.values()) or 1
    return [{"label": label, "count": count, "share": round(count * 100 / total, 1)} for label, count in counter.most_common(limit)]


def journey_dashboard(batch_id: str | None = None, product: str | None = None) -> dict:
    where, params = [], []
    if batch_id:
        where.append("batch_id=?"); params.append(batch_id)
    if product:
        where.append("product=?"); params.append(product)
    sql = "SELECT id,batch_id,filename,product,motive,score_operator,score_experience,analysis_json FROM interactions"
    if where: sql += " WHERE " + " AND ".join(where)
    with connect() as db:
        rows = [dict(row) for row in db.execute(sql, params)]
    stages = {key: Counter() for key in ("presented", "motivating", "friction", "responsibility", "root")}
    paths, root_specific, friction_count = [], 0, 0
    for row in rows:
        analysis = json.loads(row.pop("analysis_json"))
        path = interaction_path(analysis)
        for key in stages: stages[key][path[key]] += 1
        root_specific += int(path["root_confidence"] in {"Com evidência específica", "Causa comprovada", "Hipótese causal forte"})
        friction_count += int(analysis.get("cx1_friccao", {}).get("classificacao") == "Sim")
        paths.append({**row, **path})
    total = len(rows)
    funnel = [
        {"key":"presented","label":"Voz do cliente categorizada","count":sum(stages["presented"].values())},
        {"key":"motivating","label":"Causa motivadora","count":sum(v for k,v in stages["motivating"].items() if _usable(k))},
        {"key":"friction","label":"Fator da jornada","count":sum(v for k,v in stages["friction"].items() if _usable(k))},
        {"key":"responsibility","label":"Responsabilidade atribuível","count":sum(v for k,v in stages["responsibility"].items() if _usable(k))},
        {"key":"root","label":"Causa raiz categorial","count":sum(stages["root"].values())},
    ]
    products = Counter(row["product"] for row in rows)
    return {
        "filters":{"batch_id":batch_id,"product":product}, "total":total,
        "metrics":{"friction":friction_count,"root_specific":root_specific,"products":len(products),
                   "avg_experience":round(sum(row["score_experience"] for row in rows)/total,1) if total else 0},
        "funnel":funnel, "stages":{key:_top(counter) for key,counter in stages.items()},
        "products":_top(products), "paths":paths[:200],
    }
