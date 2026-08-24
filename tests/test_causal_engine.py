from app.causal_engine import CAUSAL_VERSION, analyze_causal_funnel


def test_causal_funnel_builds_traceable_hypothesis():
    analysis = {"motivo_contato":"Portabilidade","principal_insatisfacao":"Não recebi retorno sobre o andamento",
        "responsabilidade":"Processo","root_cause":{"causaraiz3_dono_jornada":"Comunicação"},
        "evidences":[{"speaker":"CLIENTE","text":"Estou aguardando há dez dias e ninguém deu retorno","is_negated":False}],"source_metadata":{}}
    result = analyze_causal_funnel(analysis)
    assert result["version"] == CAUSAL_VERSION
    assert result["mode"] == "shadow"
    assert result["journey_stage"] == "Acompanhamento"
    assert result["root_candidate"] == "Ausência ou insuficiência de atualização de status"
    assert result["evidence"]
    assert result["status"].startswith("Hipótese")


def test_causal_funnel_abstains_without_evidence():
    result = analyze_causal_funnel({"evidences": [], "motivo_contato": "Outro"})
    assert result["status"] == "Não determinada"
    assert result["confidence"] == 0
