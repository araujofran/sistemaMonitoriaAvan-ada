from app.journey import interaction_path, journey_dashboard


def test_generic_root_is_not_presented_as_technical_fact():
    analysis = {
        "motivo_contato": "Cancelamento",
        "principal_insatisfacao": "Não identificada",
        "responsabilidade": "Processo",
        "cx1_friccao": {"classificacao": "Sim"},
        "root_cause": {
            "causaraiz1_descricao": "cancelamento",
            "causaraiz2_motivo": "A evidência não permite determinar tecnicamente o mecanismo.",
            "causaraiz3_dono_jornada": "Política",
            "causaraiz4_evidencia": ["quero cancelar"],
        },
        "evidences": [{"speaker":"CLIENTE","text":"quero cancelar","category":"intent","is_negated":False}],
    }
    path = interaction_path(analysis)
    assert path["voice"] == "quero cancelar"
    assert path["root"] == "Política — mecanismo técnico não determinado"
    assert path["root_confidence"] == "Categorial"


def test_journey_dashboard_contract():
    result = journey_dashboard()
    assert len(result["funnel"]) == 5
    assert set(result["stages"]) == {"presented","motivating","friction","responsibility","root"}
    assert {"friction","root_specific","products","avg_experience"} <= result["metrics"].keys()

