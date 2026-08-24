from __future__ import annotations

from collections import Counter, defaultdict
import json
from typing import Any

from .database import connect
from .journey import interaction_path


def _class(value: Any, default: str = "Não identificado") -> str:
    if isinstance(value, dict):
        value = value.get("classificacao", default)
    return str(value or default)


def _risk_tags(value: Any) -> list[str]:
    if isinstance(value, dict): value = value.get("classificacao")
    if isinstance(value, list): values = value
    else:
        text = str(value or "").strip()
        try:
            parsed = json.loads(text.replace("'", '"')) if text.startswith("[") else None
        except (ValueError, TypeError): parsed = None
        values = parsed if isinstance(parsed, list) else [text]
    ignored = {"", "Não Aplicável", "Nao Aplicavel", "Não identificado"}
    return sorted({str(x).strip() for x in values if str(x).strip() not in ignored})


def _case(a: dict) -> str:
    impacts = a.get("impacts", {})
    high = sum(_class(v).lower() == "alto" for v in impacts.values() if isinstance(v, dict))
    exp = float(a.get("score_experiencia") or 0)
    recontact = _class(a.get("probabilidade_recontato")).lower()
    if high >= 2 or exp <= 20:
        return "Alerta Crítico"
    if high or recontact in {"alto", "alta"} or exp < 50:
        return "Caso Relevante"
    if exp < 75 or recontact in {"médio", "medio", "média", "media"}:
        return "Ponto de Atenção"
    return "Caso Controlado"


def _pillar_scores(a: dict) -> dict[str, float]:
    groups = {"relationship": 0.0, "resolution": 0.0, "cx": 0.0}
    for result in a.get("criteria", {}).values():
        group = result.get("group")
        if group in groups:
            groups[group] += float(result.get("score") or 0)
    return {"relationship": round(groups["relationship"], 1), "resolution": round(groups["resolution"], 1), "cx": round(groups["cx"], 1)}


def _top(counter: Counter, total: int | None = None, limit: int = 12) -> list[dict]:
    denominator = total if total is not None else sum(counter.values())
    denominator = denominator or 1
    return [{"label": k, "count": v, "share": round(v * 100 / denominator, 1)} for k, v in counter.most_common(limit)]


def monitoring_dashboard(batch_id: str | None = None, product: str | None = None,
                         operator: str | None = None, year: int | None = None,
                         month: int | None = None) -> dict:
    where, params = [], []
    if batch_id:
        where.append("i.batch_id=?"); params.append(batch_id)
    if product:
        where.append("i.product=?"); params.append(product)
    if year:
        where.append("substr(i.analysis_date,1,4)=?"); params.append(f"{year:04d}")
    if month:
        where.append("substr(i.analysis_date,6,2)=?"); params.append(f"{month:02d}")
    sql = """SELECT i.id,i.batch_id,i.filename,i.product,i.motive,i.score_operator,
             i.score_experience,i.analysis_date,i.created_at,i.analysis_json,b.name AS batch_name,b.uploaded_by
             FROM interactions i JOIN analysis_batches b ON b.id=i.batch_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY i.created_at DESC"
    with connect() as db:
        db_rows = [dict(row) for row in db.execute(sql, params)]

    rows, duplicate_keys = [], Counter()
    for row in db_rows:
        a = json.loads(row.pop("analysis_json"))
        attendant = str(a.get("atendente") or "Não identificado")
        if operator and attendant != operator:
            continue
        protocol = str(a.get("protocolo") or "Não identificado")
        duplicate_keys[protocol if protocol not in {"", "Não identificado"} else row["filename"]] += 1
        path = a.get("journey") or interaction_path(a)
        pillars = _pillar_scores(a)
        root = a.get("root_cause", {})
        nlp = a.get("nlp", {})
        impacts = {k: _class(v) for k, v in a.get("impacts", {}).items()}
        regulatory_tags = _risk_tags((a.get("impacts", {}).get("imp5_risco_reclamacao") or {}))
        rows.append({
            **row, "operator": attendant, "protocol": protocol,
            "summary": a.get("resumo", ""), "dissatisfaction": a.get("principal_insatisfacao", ""),
            "operator_class": a.get("classificacao_operador", ""), "resolved": _class(a.get("atendimento_resolutivo")),
            "effort": _class(a.get("nivel_esforco_cliente")), "recontact": _class(a.get("probabilidade_recontato")),
            "customer_mood": _class(a.get("humor_cliente")), "responsibility": a.get("responsabilidade", "Não identificado"),
            "friction": _class(a.get("cx1_friccao")), "case": _case(a), "pillars": pillars,
            "impacts": impacts, "regulatory_risks": regulatory_tags,
            "root_cause": root.get("causaraiz1_descricao", path.get("root", "Não identificado")),
            "root_reason": root.get("causaraiz2_motivo", ""), "root_owner": root.get("causaraiz3_dono_jornada", ""),
            "root_evidence": root.get("causaraiz4_evidencia", []), "journey": path,
            "nlp": nlp, "motive_detail": a.get("motivo_contato",""),
            "agent_mood": _class(a.get("humor_atendente")), "criteria": list(a.get("criteria", {}).values()),
            "evidences": a.get("evidences", [])[:100], "ces": a.get("ces", {}),
            "responsibility_reason": a.get("responsabilidade_motivo", ""),
        })

    total = len(rows)
    avg = lambda key: round(sum(float(r[key] or 0) for r in rows) / total, 1) if total else 0
    resolved_count = sum(r["resolved"].lower() == "sim" for r in rows)
    cases = Counter(r["case"] for r in rows)
    responsibilities = Counter(r["responsibility"] for r in rows)
    recontacts = Counter(r["recontact"] for r in rows)
    efforts = Counter(r["effort"] for r in rows)
    products = Counter(r["product"] for r in rows)
    roots = Counter(r["root_cause"] for r in rows)
    duplicates = sum(v - 1 for v in duplicate_keys.values() if v > 1)

    by_operator: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_operator[row["operator"]].append(row)
    operators = []
    for name, items in by_operator.items():
        n = len(items)
        operators.append({
            "name": name, "interactions": n, "protocols": len({x["protocol"] for x in items}),
            "avg_operator": round(sum(float(x["score_operator"] or 0) for x in items) / n, 1),
            "avg_experience": round(sum(float(x["score_experience"] or 0) for x in items) / n, 1),
            "resolution_rate": round(sum(x["resolved"].lower() == "sim" for x in items) * 100 / n, 1),
            "alerts": sum(x["case"] == "Alerta Crítico" for x in items),
            "pillars": {key: round(sum(x["pillars"][key] for x in items) / n, 1) for key in ("relationship", "resolution", "cx")},
            "sample": "Amostra robusta" if n >= 3 else "Amostra limitada" if n == 2 else "Resultado pontual",
        })
    operators.sort(key=lambda x: (-x["avg_operator"], -x["interactions"]))

    nlp_rows = [r for r in rows if r.get("nlp")]
    nlp_confidence = round(sum(float(r["nlp"].get("confidence",0)) for r in nlp_rows)/len(nlp_rows),3) if nlp_rows else 0
    nlp_abstained = sum(bool(r["nlp"].get("audit",{}).get("abstained")) for r in nlp_rows)
    concordant = sum(str(r.get("motive_detail","")).lower() in str(r["nlp"].get("primary_topic","")).lower() or
                     str(r["nlp"].get("primary_topic","")).lower() in str(r.get("motive_detail","")).lower() for r in nlp_rows)

    risk_keys = {
        "imp1_potencial_reclamacao": "Reclamação", "imp2_potencial_cancelamento": "Cancelamento",
        "imp3_potencial_contestacao": "Contestação", "imp4_potencial_ouvidoria": "Ouvidoria",
        "imp5_risco_reclamacao": "Risco regulatório",
    }
    risks = []
    for key, label in risk_keys.items():
        if key == "imp5_risco_reclamacao":
            levels = Counter(tag for r in rows for tag in r["regulatory_risks"])
            affected = sum(bool(r["regulatory_risks"]) for r in rows)
            risks.append({"key":key,"label":label,"levels":dict(levels),"high":affected,"affected":affected})
        else:
            levels = Counter(r["impacts"].get(key, "Não Aplicável") for r in rows)
            risks.append({"key":key,"label":label,"levels":dict(levels),"high":levels.get("Alto",0),"affected":sum(v for k,v in levels.items() if k != "Não Aplicável")})

    failed_criteria = Counter()
    for row in rows:
        # Opportunities are intentionally tied to stored findings, never invented from score alone.
        if row["root_cause"] and row["root_cause"] != "Não identificado":
            failed_criteria[row["root_cause"]] += 1

    return {
        "filters": {"batch_id": batch_id, "product": product, "operator": operator, "year": year, "month": month},
        "kpis": {"interactions": total, "unique_protocols": len({r["protocol"] for r in rows}),
                 "avg_operator": avg("score_operator"), "avg_experience": avg("score_experience"),
                 "resolution_rate": round(resolved_count * 100 / total, 1) if total else 0,
                 "critical_alerts": cases.get("Alerta Crítico", 0), "duplicates": duplicates},
        "distributions": {"cases": _top(cases, total), "responsibilities": _top(responsibilities, total),
                          "recontacts": _top(recontacts, total), "efforts": _top(efforts, total),
                          "products": _top(products, total), "root_causes": _top(roots, total)},
        "operators": operators, "interactions": rows, "risks": risks,
        "data_quality": {"operator_identified":sum(r["operator"] != "Não identificado" for r in rows),
                         "operator_missing":sum(r["operator"] == "Não identificado" for r in rows),
                         "operator_coverage":round(sum(r["operator"] != "Não identificado" for r in rows)*100/total,1) if total else 0},
        "insights": {
            "separation": round(avg("score_operator") - avg("score_experience"), 1),
            "high_recontact": recontacts.get("Alto", 0) + recontacts.get("Alta", 0),
            "systemic": sum(responsibilities[x] for x in ("Plataforma", "Política", "Processo")),
            "training_topics": _top(failed_criteria, total, 5),
            "goals": {
                "score_operator":{"current":avg("score_operator"),"target":round(min(100,avg("score_operator")+8),1),"direction":"increase","unit":"pontos"},
                "experience":{"current":avg("score_experience"),"target":round(min(100,avg("score_experience")+10),1),"direction":"increase","unit":"pontos"},
                "resolution":{"current":round(resolved_count*100/total,1) if total else 0,"target":round(min(100,(resolved_count*100/total if total else 0)+15),1),"direction":"increase","unit":"%"},
                "critical_alerts":{"current":cases.get("Alerta Crítico",0),"target":max(0,round(cases.get("Alerta Crítico",0)*.7)),"direction":"decrease","unit":"casos"},
            },
        },
        "nlp_audit": {"processed":len(nlp_rows),"confidence_average":nlp_confidence,"abstained":nlp_abstained,
                      "regex_nlp_concordant":concordant,"divergent_or_complementary":len(nlp_rows)-concordant,
                      "mode":"shadow","score_authority":"regex"},
    }


def monitoring_filters() -> dict:
    with connect() as db:
        batches = [dict(r) for r in db.execute("SELECT id,name,created_at FROM analysis_batches ORDER BY created_at DESC")]
        products = [r[0] for r in db.execute("SELECT DISTINCT product FROM interactions WHERE product IS NOT NULL ORDER BY product")]
        analyses = [json.loads(r[0]) for r in db.execute("SELECT analysis_json FROM interactions")]
        years = [r[0] for r in db.execute("SELECT DISTINCT substr(analysis_date,1,4) FROM interactions WHERE analysis_date IS NOT NULL ORDER BY 1 DESC")]
    return {"batches": batches, "products": products, "operators": sorted({str(a.get('atendente') or 'Não identificado') for a in analyses}), "years": years}


def monitoring_answer(question: str, **filters: Any) -> dict:
    data = monitoring_dashboard(**filters)
    q = question.lower()
    k, ops, ins = data["kpis"], data["operators"], data["insights"]
    if not k["interactions"]:
        answer = "Não há análises no banco para os filtros selecionados."
    elif any(x in q for x in ("melhor", "operador", "ranking")):
        eligible = [x for x in ops if x["interactions"] >= 3] or ops
        best = max(eligible, key=lambda x: x["avg_operator"])
        answer = f"{best['name']} tem o melhor resultado elegível: {best['avg_operator']}/100 em {best['interactions']} monitorias."
    elif any(x in q for x in ("risco", "alerta", "reclama")):
        answer = f"Há {k['critical_alerts']} alertas críticos em {k['interactions']} atendimentos e {ins['high_recontact']} casos com recontato alto."
    elif any(x in q for x in ("experiência", "experiencia", "score")):
        answer = f"O Score Operador médio é {k['avg_operator']} e o Score Experiência é {k['avg_experience']}; a diferença é {ins['separation']} pontos."
    elif any(x in q for x in ("duplic", "repet")):
        answer = f"Foram identificados {k['duplicates']} registros duplicados pelos identificadores disponíveis."
    elif any(x in q for x in ("trein", "capacita", "desenvolv")):
        topics = ", ".join(x["label"] for x in ins["training_topics"][:3]) or "nenhum tema recorrente comprovado"
        answer = f"Os temas prioritários derivados das causas registradas são: {topics}."
    else:
        answer = f"A base filtrada contém {k['interactions']} atendimentos, resolução de {k['resolution_rate']}% e {k['critical_alerts']} alertas críticos."
    return {"answer": answer, "evidence": {"filters": data["filters"], "kpis": k}, "source": "Banco de análises consolidado"}
