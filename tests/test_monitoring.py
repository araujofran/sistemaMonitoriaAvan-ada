import json

from app.database import connect
from app.monitoring import monitoring_answer, monitoring_dashboard, monitoring_filters


def _analysis(operator: str, protocol: str, score: float, experience: float, resolved: str = "Sim") -> dict:
    return {
        "atendente": operator, "protocolo": protocol, "resumo": "Resumo auditável",
        "principal_insatisfacao": "Prazo informado pelo cliente", "classificacao_operador": "Atende as expectativas",
        "score_operador": score, "score_experiencia": experience,
        "atendimento_resolutivo": {"classificacao": resolved}, "nivel_esforco_cliente": {"classificacao": "Médio"},
        "probabilidade_recontato": {"classificacao": "Médio"}, "humor_cliente": {"classificacao": "Neutro"},
        "responsabilidade": "Processo", "cx1_friccao": {"classificacao": "Sim"}, "criteria": {},
        "impacts": {"imp1_potencial_reclamacao": {"classificacao": "Baixo"}},
        "root_cause": {"causaraiz1_descricao": "Prazo", "causaraiz2_motivo": "Evidência explícita",
                       "causaraiz3_dono_jornada": "Processo", "causaraiz4_evidencia": ["aguardando prazo"]},
        "evidences": [], "motivo_contato": "Prazo",
    }


def _insert(operator="Ana", protocol="123", score=80, experience=60):
    analysis = _analysis(operator, protocol, score, experience)
    with connect() as db:
        db.execute("INSERT INTO analysis_batches(id,name,status,total_files) VALUES('b1','Lote teste','DONE',1)")
        db.execute("""INSERT INTO interactions(id,batch_id,filename,content_hash,analysis_status,score_operator,
                   score_experience,product,motive,analysis_json,analysis_date)
                   VALUES('i1','b1','atendimento.txt','hash','VALID',?,?,?,?,?,?)""",
                   (score, experience, "Câmbio", "Prazo", json.dumps(analysis), "2026-08-23"))


def test_monitoring_dashboard_aggregates_database():
    _insert()
    result = monitoring_dashboard()
    assert result["kpis"]["interactions"] == 1
    assert result["kpis"]["avg_operator"] == 80
    assert result["operators"][0]["name"] == "Ana"
    assert result["interactions"][0]["root_cause"] == "Prazo"


def test_monitoring_filters_and_chat_use_same_database():
    _insert()
    assert monitoring_filters()["products"] == ["Câmbio"]
    response = monitoring_answer("Qual é o score?")
    assert "80.0" in response["answer"]
    assert response["evidence"]["kpis"]["interactions"] == 1
