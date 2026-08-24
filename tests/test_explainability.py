import json

from app.database import connect
from app.explainability import explainability_dashboard
from app.scoring_policy import scores_for


def _criterion(code, name, group, classification, score=0, evidence=None):
    return {"code": code, "name": name, "group": group, "classification": classification,
            "score": score, "bonus": 0, "evidence": evidence or [], "justification": "Regra de teste"}


def _insert(interaction_id, official_score, noncompliance_code, evidence=None, metadata=None):
    criteria = {
        "quality": _criterion("quality", "Qualidade", "relationship", "Sim", 75),
        noncompliance_code: _criterion(noncompliance_code, "Inaderência", "noncompliance", "Sim", evidence=evidence),
        "inv_extra1": _criterion("inv_extra1", "Extra", "extra", "Não"),
    }
    analysis = {"score_operador": official_score, "atendente": "Ana", "criteria": criteria,
                "nlp": {"primary_topic": "Prazo", "sentiment": {"label": "Neutro"},
                        "confidence": .9, "version": "test", "audit": {"abstained": False}}}
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO analysis_batches(id,name,status,total_files) VALUES('b1','Teste','DONE',2)")
        db.execute("""INSERT INTO interactions(id,batch_id,filename,content_hash,analysis_status,score_operator,
                   score_experience,product,motive,analysis_json,metadata_json,analysis_date)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (interaction_id, "b1", f"{interaction_id}.txt", interaction_id, "VALID", official_score,
                    50, "Consignado", "Prazo", json.dumps(analysis), json.dumps(metadata or {}), "2026-08-24"))


def test_absence_only_is_released_in_hybrid_simulation():
    _insert("absence", 0, "at_inad_compr2", metadata={"PROTOCOLO": "123456"})
    result = explainability_dashboard()
    assert result["summary"]["official"]["zeros"] == 1
    assert result["summary"]["simulated"]["zeros"] == 0
    assert result["summary"]["released_by_hybrid"] == 1
    assert result["interactions"][0]["protocol_in_metadata"] is True


def test_explicit_severe_evidence_keeps_zero():
    _insert("explicit", 0, "at_inad_compr7", evidence=["cobrança indevida"])
    result = explainability_dashboard(status="hybrid_zero")
    assert result["summary"]["simulated"]["zeros"] == 1
    assert result["result_count"] == 1
    assert result["interactions"][0]["triggers"][0]["basis"] == "Evidência Regex explícita"


def test_policy_scores_keep_rigid_and_hybrid_versions():
    criteria = {
        "quality": _criterion("quality", "Qualidade", "relationship", "Sim", 75),
        "at_inad_compr2": _criterion("at_inad_compr2", "Protocolo", "noncompliance", "Sim"),
        "inv_extra1": _criterion("inv_extra1", "Extra", "extra", "Não"),
    }
    rigid, hybrid = scores_for({"criteria": criteria})
    assert rigid == 0
    assert hybrid == 75
