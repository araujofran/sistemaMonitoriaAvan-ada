from app.nlp_engine import NLP_VERSION, analyze_nlp


def test_nlp_extracts_context_topics_entities_and_audit():
    text = "Cliente: Estou frustrada, a remessa de R$ 250,00 está bloqueada há três dias úteis. Quero o estorno."
    result = analyze_nlp(text)
    assert result["version"] == NLP_VERSION
    assert result["sentiment"]["label"] == "Negativo"
    assert "R$ 250,00" in result["entities"]["valores"]
    assert result["topics"]
    assert result["confidence"] > 0


def test_nlp_abstains_without_semantic_evidence():
    result = analyze_nlp("Cliente falou com o atendente e encerrou a ligação.")
    assert result["audit"]["abstained"] is True
    assert result["primary_topic"] == "Não determinado"
