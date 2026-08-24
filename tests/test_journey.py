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
    assert path["root"] == "Dificuldade ou necessidade de cancelamento/estorno"
    assert path["root_confidence"].startswith("Hipótese causal")


def test_journey_dashboard_contract():
    result = journey_dashboard()
    assert len(result["funnel"]) == 5
    assert set(result["stages"]) == {"presented","motivating","friction","responsibility","root"}
    assert {"friction","root_specific","products","avg_experience"} <= result["metrics"].keys()


def test_numeric_sentiment_code_is_not_presented_as_cause():
    analysis = {
        "source_metadata": {"SENTIMENTO_CLIENTE": 2, "CATEGORIA": "Cancelamento Desistência"},
        "motivo_contato": "Cancelamento", "principal_insatisfacao": "Cliente quer cancelar",
        "responsabilidade": "Pessoa", "cx1_friccao": {"classificacao": "Não"},
        "root_cause": {"causaraiz2_motivo": "Motivo confirmado", "causaraiz3_dono_jornada": "Comunicação"},
        "evidences": [],
    }
    assert interaction_path(analysis)["presented"] == "Cancelamento Desistência"


def test_numeric_category_falls_back_to_detected_motive():
    analysis = {
        "source_metadata": {"CATEGORIA": "3"}, "motivo_contato": "Quitação",
        "principal_insatisfacao": "Prazo", "responsabilidade": "Processo",
        "cx1_friccao": {"classificacao": "Não"},
        "root_cause": {"causaraiz2_motivo": "Motivo confirmado", "causaraiz3_dono_jornada": "Processo"},
        "evidences": [],
    }
    assert interaction_path(analysis)["presented"] == "Quitação"
