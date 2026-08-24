from app.catalog import DETECTORS
from app.contract_validator import validate_analysis
from app.service import analyze_text


SAMPLE = """#Atendente: Bom dia, meu nome é Ana. Pode confirmar seu CPF 123.456.789-09, CEP 01001-000, telefone (11) 91234-5678 e e-mail ana@example.com?
#Cliente: Meu nome é Francisco. Quero a segunda via do boleto.
#Atendente: Entendi que precisa da segunda via, correto? Vou verificar.
#Atendente: Foi enviado por e-mail. Posso ajudar em algo mais? Responda à pesquisa de satisfação. Seu protocolo é 123456789.
#Cliente: Excelente atendimento, você me ajudou muito.
"""


def test_catalog_contract():
    assert 80 <= len(DETECTORS) <= 150
    assert len({d.regex_id for d in DETECTORS}) == len(DETECTORS)


def test_full_contract_and_scores():
    _, result = analyze_text(SAMPLE)
    assert validate_analysis(result) == []
    assert len([x for x in result["criteria"].values() if x["group"] == "relationship"]) == 14
    assert len([x for x in result["criteria"].values() if x["group"] == "resolution"]) == 2
    assert len([x for x in result["criteria"].values() if x["group"] == "cx"]) == 9
    assert 0 <= result["score_operador"] <= 100
    assert 0 <= result["score_experiencia"] <= 100
    assert result["atendente"] == "Ana"
    assert "meu nome é Ana" in result["atendente_evidencia"]


def test_negation_does_not_become_transfer():
    _, result = analyze_text("#Atendente: Não vou transferir a senhora.\n#Cliente: Certo.")
    active = [e for e in result["evidences"] if e["detector"] == "transferencia_realizada" and not e["is_negated"]]
    assert active == []
    assert any(e["detector"] == "transferencia_negada" for e in result["evidences"])


def test_cpf_is_not_enough_for_confirmation():
    _, result = analyze_text("#Atendente: Pode confirmar seu CPF 123.456.789-09?\n#Cliente: Sim.")
    assert result["criteria"]["at_cx_intro2"]["classification"] == "Não"
