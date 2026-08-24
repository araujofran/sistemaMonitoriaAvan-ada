from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
import re
from typing import Any

from .criteria import CRITERIA
from .domain import CriterionResult, Evidence, Turn

NO_EVIDENCE = "Não foi localizada evidência suficiente na transcrição para confirmar este critério."


def _active(evidence: list[Evidence], name: str) -> list[Evidence]:
    return [e for e in evidence if e.detector == name and not e.is_negated]


def _texts(items: list[Evidence], limit: int = 3) -> list[str]:
    return [e.text for e in items[:limit]]


def _result(code: str, classification: str, evidence: list[Evidence] = (), reason: str | None = None) -> CriterionResult:
    name, group, weight, partial = CRITERIA[code]
    if classification == "Parcial" and not partial:
        classification = "Não"
    factor = {"Sim": 1, "Não Aplicável": 1, "Parcial": .5, "Não": 0}[classification]
    penalty = -100 if group == "noncompliance" and classification == "Sim" else 0
    bonus = 1 if group == "extra" and classification == "Sim" else 0
    ev = _texts(list(evidence))
    justification = reason or (f"Evidência localizada: “{ev[0]}”." if ev else NO_EVIDENCE)
    return CriterionResult(code, name, group, weight, classification, factor, round(weight * factor, 2), justification, ev, penalty, bonus)


def evaluate(turns: list[Turn], evidence: list[Evidence], filename: str) -> dict[str, Any]:
    has = lambda name: bool(_active(evidence, name))
    ev = lambda name: _active(evidence, name)
    results: dict[str, CriterionResult] = {}
    # Relationship: absence of adverse evidence cannot prove subjective behavior; only objective criteria default positive.
    results["at_rel_cord1"] = _result("at_rel_cord1", "Sim" if has("tratamento_nome") else "Não", ev("tratamento_nome"))
    results["at_rel_cord2"] = _result("at_rel_cord2", "Sim" if has("desculpas") else "Não Aplicável", ev("desculpas"), "Não houve situação explícita que exigisse desculpas." if not has("desculpas") else None)
    results["at_rel_cord3"] = _result("at_rel_cord3", "Sim" if any(has(x) for x in ("saudacao","acolhimento","por_favor")) else "Não", ev("acolhimento") or ev("saudacao"))
    results["at_rel_cord4"] = _result("at_rel_cord4", "Sim" if has("empatia") else "Não Aplicável", ev("empatia"), "Não houve emoção explícita que tornasse a empatia avaliável." if not has("empatia") else None)
    for code, name in (("at_rel_cord5","Paciência"),("at_rel_cord6","Sem interrupção"),("at_rel_cord7","Calma")):
        results[code] = _result(code, "Não Aplicável", reason=f"{name} não é determinável com segurança em transcrição sem marcação acústica/temporal.")
    results["at_rel_ling1"] = _result("at_rel_ling1", "Não" if has("ofensiva") else "Sim", ev("ofensiva"), "Não houve linguagem ofensiva explícita do atendente." if not has("ofensiva") else None)
    tic_count = sum(len(ev(n)) for n in ("vicio_ne","vicio_ta","vicio_tipo_assim","vicio_entendeu","vicio_beleza"))
    results["at_rel_ling2"] = _result("at_rel_ling2", "Não" if tic_count >= 3 else "Sim", reason=f"Foram localizados {tic_count} vícios de linguagem do atendente.")
    results["at_rel_ling3"] = _result("at_rel_ling3", "Sim" if has("seguranca_fala") else "Não", ev("seguranca_fala"))
    results["at_rel_ling4"] = _result("at_rel_ling4", "Não" if has("gerundismo") else "Sim", ev("gerundismo"), "Nenhuma ocorrência de gerundismo configurado foi localizada." if not has("gerundismo") else None)
    results["at_rel_ling5"] = _result("at_rel_ling5", "Sim" if any(has(x) for x in ("resolucao_explicita","proximo_passo","seguranca_fala")) else "Não", reason="A comunicação trouxe orientação ou confirmação objetiva." if any(has(x) for x in ("resolucao_explicita","proximo_passo","seguranca_fala")) else NO_EVIDENCE)
    agent_words = sum(len(t.text_original.split()) for t in turns if t.speaker == "ATENDENTE")
    results["at_rel_cond1"] = _result("at_rel_cond1", "Sim" if agent_words < 1200 else "Parcial", reason=f"A fala do atendente contém {agent_words} palavras; não foram encontrados desvios objetivos de concisão." )
    results["at_rel_cond2"] = _result("at_rel_cond2", "Sim" if has("seguranca_fala") or has("resolucao_explicita") else "Não", reason="A condução permaneceu associada à demanda identificada." if has("seguranca_fala") or has("resolucao_explicita") else NO_EVIDENCE)

    unresolved, resolved, recontact = has("nao_resolucao"), has("resolucao_explicita"), has("recontato")
    next_step = has("proximo_passo") or has("prazo")
    results["at_resol_solic1"] = _result("at_resol_solic1", "Sim" if resolved and next_step else "Parcial" if resolved or next_step else "Não", ev("resolucao_explicita") + ev("proximo_passo"))
    results["at_resol_solic2"] = _result("at_resol_solic2", "Não" if recontact else "Sim" if resolved else "Parcial", ev("recontato") + ev("resolucao_explicita"))
    results["at_cx_intro1"] = _result("at_cx_intro1", "Sim" if has("saudacao") and has("identificacao_atendente") else "Parcial" if has("saudacao") or has("identificacao_atendente") else "Não", ev("saudacao") + ev("identificacao_atendente"))
    data_names = {e.detector for e in evidence if e.detector in {"cpf","cep","telefone","email","data_nascimento","agencia","conta","rg","nome_mae","endereco"}}
    results["at_cx_intro2"] = _result("at_cx_intro2", "Sim" if len(data_names) >= 4 and has("confirmacao_dado") else "Parcial" if len(data_names) >= 2 and has("confirmacao_dado") else "Não", reason=f"Foram identificados {len(data_names)} tipos de dados cadastrais no contexto de validação; o mínimo para Sim é quatro.")
    results["at_cx_compr1"] = _result("at_cx_compr1", "Sim" if has("pergunta_sondagem") else "Não", ev("pergunta_sondagem"))
    intents = [e for e in evidence if e.category == "intent" and not e.is_negated]
    results["at_cx_compr2"] = _result("at_cx_compr2", "Sim" if intents else "Não", intents)
    repeated = has("retrabalho")
    results["at_cx_compr3"] = _result("at_cx_compr3", "Não" if repeated else "Sim", ev("retrabalho"), "Não houve marcador explícito de repetição de informações." if not repeated else None)
    results["at_cx_compr4"] = _result("at_cx_compr4", "Sim" if has("validacao_entendimento") else "Não", ev("validacao_entendimento"))
    results["at_cx_classif1"] = _result("at_cx_classif1", "Não" if unresolved or recontact else "Sim" if resolved else "Parcial", ev("nao_resolucao") + ev("recontato") + ev("resolucao_explicita"))
    results["at_cx_classif2"] = _result("at_cx_classif2", "Sim" if next_step else "Não", ev("proximo_passo") + ev("prazo"))
    results["at_cx_classif3"] = _result("at_cx_classif3", "Não" if unresolved else "Sim" if resolved else "Parcial", ev("nao_resolucao") + ev("resolucao_explicita"))

    deadline_applicable = has("prazo") or has("proximo_passo")
    noncomp = {
        "at_inad_compr1": (not has("convite_pesquisa"), ev("convite_pesquisa"), "O encerramento não apresentou convite explícito para pesquisa."),
        "at_inad_compr2": (not has("protocolo_informado") and not has("protocolo"), ev("protocolo_informado") + ev("protocolo"), "Não foi localizado protocolo informado ao cliente."),
        "at_inad_compr3": (deadline_applicable and not has("prazo"), ev("prazo"), "Havia orientação operacional, mas não foi localizado prazo."),
        "at_inad_compr4": (has("alteracao_prazo"), ev("alteracao_prazo"), None),
        "at_inad_compr5": (not has("encerramento"), ev("encerramento"), "Não foi localizado encerramento formal."),
        "at_inad_compr6": (has("ofensiva"), ev("ofensiva"), None),
        "at_inad_compr7": (has("prejuizo"), ev("prejuizo"), None),
    }
    for code, (failed, evid, reason) in noncomp.items():
        if code == "at_inad_compr3" and not deadline_applicable:
            results[code] = _result(code, "Não Aplicável", reason="A interação não apresentou SLA ou prazo obrigatório identificável.")
        else:
            results[code] = _result(code, "Sim" if failed else "Não", evid, reason or ("A falha foi comprovada por evidência explícita." if failed else "Nenhuma ocorrência identificada."))
    results["inv_extra1"] = _result("inv_extra1", "Sim" if has("elogio_explicito") else "Não", ev("elogio_explicito"), "Não houve elogio excepcional explícito do cliente." if not has("elogio_explicito") else None)

    # Scores: critical noncompliance zeroes the monitoring result; bonus is capped at 100.
    base = sum(r.score for r in results.values() if r.group in {"relationship","resolution","cx"})
    critical = any(r.group == "noncompliance" and r.classification == "Sim" for r in results.values())
    score_operator = 0 if critical else min(100, base + results["inv_extra1"].bonus)
    classification = "Extraordinário" if score_operator == 100 else "Supera as expectativas" if score_operator >= 85 else "Atende as expectativas" if score_operator >= 70 else "Pode Melhorar" if score_operator >= 50 else "Pode Melhorar Muito"
    effort = "Alto" if recontact or has("mudanca_canal") else "Médio" if has("friccao") else "Baixo"
    friction = "Sim" if has("friccao") or recontact or has("mudanca_canal") else "Não"
    complaint_high = has("reclamacao") or has("ouvidoria") or has("bacen") or has("procon") or has("judicial")
    exp = (30 if resolved and not unresolved else 0) + (30 if results["at_cx_classif1"].classification == "Sim" else 0) + {"Baixo":20,"Médio":10,"Alto":0}[effort] + (20 if friction == "Não" else 0) - (50 if complaint_high else 0)
    score_experience = max(0, min(100, exp))
    products = [e.detector for e in evidence if e.category == "products" and not e.is_negated]
    motive = intents[0].detector if intents else "Não identificado"
    name_match = next((re.search(r"(?:meu nome é|me chamo)\s+([A-ZÀ-Ý][a-zà-ÿ]+)", t.text_original, re.I) for t in turns if t.speaker == "CLIENTE"), None)
    risks = [label for detector,label in (("bacen","BACEN"),("procon","Consumidor"),("consumidor_gov","Consumidor"),("judicial","Judicial"),("fraude","Fraude")) if has(detector)] or ["Não Aplicável"]
    responsibility = "Plataforma" if has("erro_plataforma") or has("indisponibilidade") else "Política" if has("politica") else "Pessoa" if any(r.classification in {"Não","Parcial"} for r in results.values() if r.group in {"relationship","resolution","cx"}) else "Não identificado"
    return {
        "analysis_version": "1.0.0", "filename": filename, "data_interacao": datetime.now().isoformat(),
        "nome_cliente": name_match.group(1) if name_match else "Não identificado", "atendente": "Não identificado",
        "cpf": next((e.text for e in evidence if e.detector == "cpf"), "Não identificado"),
        "protocolo": next((re.sub(r"\D", "", e.text) for e in evidence if e.detector == "protocolo"), "Não identificado"),
        "produto_principal": products[0].replace("_", " ").title() if products else "Não identificado", "motivo_contato": motive.replace("_", " ").title(),
        "resumo": f"Atendimento sobre {motive.replace('_',' ')}; {'houve resolução explícita' if resolved else 'não houve confirmação explícita de resolução'}.",
        "principal_insatisfacao": _texts(ev("reclamacao") + ev("friccao"), 1)[0] if ev("reclamacao") or ev("friccao") else "Não identificada",
        "criteria": {k: v.to_dict() for k,v in results.items()}, "score_operador": round(score_operator,2), "classificacao_operador": classification,
        "score_experiencia": score_experience, "atendimento_resolutivo": {"classificacao":"Sim" if resolved and not unresolved else "Não", "justificativa": "Baseado em marcador explícito de resolução/não resolução."},
        "nivel_esforco_cliente": {"classificacao":effort,"justificativa":"Derivado de recontato, mudança de canal e sinais de fricção."},
        "probabilidade_recontato": {"classificacao":"Alto" if recontact or unresolved else "Baixo" if resolved else "Médio","justificativa":"Baseada em recontato e desfecho explícitos."},
        "humor_cliente": {"classificacao":"Negativo" if has("raiva") or has("frustracao") or has("reclamacao") else "Positivo" if has("elogio_explicito") or has("alivio") else "Neutro","justificativa":"Somente marcadores emocionais explícitos foram considerados."},
        "humor_atendente": {"classificacao":"Negativo" if has("ofensiva") else "Neutro","justificativa":"Sem inferência emocional além de linguagem explícita."},
        "ces": {"ces1_canal":{"classificacao":"Sim" if has("mudanca_canal") else "Não","justificativa":"Mudança efetiva/orientada de canal."},"ces2_retrabalho":{"classificacao":"Sim" if recontact or unresolved else "Não","justificativa":"Potencial de novo contato."},"ces3_reduziu":{"classificacao":"Sim" if next_step and not recontact else "Não","justificativa":"Clareza de próximos passos sem recontato."}},
        "cx1_friccao": {"classificacao":friction,"justificativa":"Derivada de dificuldade, recontato ou mudança de canal."},
        "impacts": {"imp1_potencial_reclamacao":{"classificacao":"Alto" if complaint_high else "Baixo","justificativa":"Sinais explícitos de reclamação/regulador."},"imp2_potencial_cancelamento":{"classificacao":"Alto" if has("cancelamento") else "Baixo","justificativa":"Intenção explícita de cancelamento."},"imp3_potencial_contestacao":{"classificacao":"Alto" if has("contestacao") else "Baixo","justificativa":"Intenção explícita de contestação."},"imp4_potencial_ouvidoria":{"classificacao":"Alto" if has("ouvidoria") else "Baixo","justificativa":"Menção explícita à Ouvidoria."},"imp5_risco_reclamacao":{"classificacao":risks,"justificativa":"Somente riscos regulatórios mencionados explicitamente."}},
        "responsabilidade": responsibility, "responsabilidade_motivo":"Classificação determinística baseada em evidência explícita de plataforma, política ou conduta.",
        "root_cause": {"causaraiz1_descricao": motive.replace("_"," "),"causaraiz2_motivo":"A evidência permite identificar a categoria da falha, mas não permite determinar tecnicamente o componente ou mecanismo que a originou.","causaraiz3_dono_jornada":"Sistema" if responsibility=="Plataforma" else "Política" if responsibility=="Política" else "Comunicação" if responsibility=="Pessoa" else "Outros","causaraiz4_evidencia":_texts([e for e in evidence if e.category in {"intent","operational","friction"}],2) or ["Evidência técnica insuficiente."]},
        "evidences": [asdict(e) for e in evidence],
    }

