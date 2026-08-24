from __future__ import annotations

import re
import unicodedata
from typing import Any

CAUSAL_VERSION = "causal-shadow-1.0.0"

PATTERNS = (
    ("Prazo e acompanhamento", r"\b(?:demor|prazo|aguard|retorno|andamento|status|dias? uteis)\w*", "Acompanhamento", "Ausência ou insuficiência de atualização de status"),
    ("Comunicação e orientação", r"\b(?:nao entendi|duvida|explic|inform|orient|ninguem avis|nao sabia)\w*", "Orientação", "Orientação insuficiente ou informação pouco clara"),
    ("Acesso e plataforma", r"\b(?:erro|indispon|sistema|aplicativo|app|site|login|token|trav)\w*", "Canal digital", "Indisponibilidade ou dificuldade de acesso no canal"),
    ("Cancelamento e desistência", r"\b(?:cancel|desist|estorn|devolu)\w*", "Cancelamento", "Dificuldade ou necessidade de cancelamento/estorno"),
    ("Cobrança ou pagamento", r"\b(?:cobran|boleto|pagamento|parcela|valor|saldo devedor)\w*", "Pagamento", "Divergência ou dificuldade no fluxo de cobrança/pagamento"),
    ("Proposta e contratação", r"\b(?:proposta|contrat|aprova|formaliza|averba)\w*", "Contratação", "Falha ou pendência percebida no processamento da proposta"),
    ("Protocolo e registro", r"\b(?:protocolo|registro|chamado)\w*", "Atendimento", "Ausência ou dificuldade de rastreamento do atendimento"),
)


def _plain(value: Any) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(value or "").lower()) if unicodedata.category(c) != "Mn")


def _customer_evidence(analysis: dict) -> list[str]:
    found = []
    for item in analysis.get("evidences", []):
        if item.get("speaker") == "CLIENTE" and not item.get("is_negated"):
            text = str(item.get("text") or "").strip()
            if len(text) >= 4 and text not in found:
                found.append(text[:300])
    for value in (analysis.get("principal_insatisfacao"), analysis.get("motivo_contato")):
        text = str(value or "").strip()
        if len(text) >= 4 and "nao identific" not in _plain(text) and text not in found:
            found.append(text[:300])
    return found


def analyze_causal_funnel(analysis: dict) -> dict:
    evidence = _customer_evidence(analysis)
    corpus = _plain(" ".join(evidence))
    matches = []
    for category, pattern, stage, candidate in PATTERNS:
        hits = sorted(set(re.findall(pattern, corpus, re.I)))
        if hits:
            matches.append((len(hits), category, stage, candidate, hits))
    matches.sort(reverse=True)
    voice = evidence[0] if evidence else "Sem fala causal suficiente"
    if not matches:
        return {"version":CAUSAL_VERSION,"mode":"shadow","voice":voice,"expressed_problem":"Não determinado",
                "journey_stage":"Não determinada","friction":"Não determinada","root_candidate":"Causa raiz não determinada",
                "responsibility":"Não atribuída","confidence":0.0,"status":"Não determinada","evidence":evidence[:3],
                "limitations":["Não há evidência textual suficiente para sustentar uma hipótese causal."]}
    _, category, stage, candidate, hits = matches[0]
    metadata_keys = _plain(" ".join(map(str, analysis.get("source_metadata", {}).keys())))
    direct_metadata = any(k in metadata_keys for k in ("causa_raiz", "incidente", "motivo_tecnico"))
    confidence = min(.92, .52 + .08 * len(hits) + .05 * min(len(evidence), 3))
    status = "Causa comprovada" if direct_metadata else "Hipótese causal forte" if confidence >= .72 else "Hipótese causal fraca"
    owner = str((analysis.get("root_cause") or {}).get("causaraiz3_dono_jornada") or analysis.get("responsabilidade") or "Não atribuída")
    return {"version":CAUSAL_VERSION,"mode":"shadow","voice":voice,"expressed_problem":category,"journey_stage":stage,
            "friction":category,"root_candidate":candidate,"responsibility":owner,"confidence":round(confidence,2),"status":status,
            "evidence":evidence[:3],"matched_signals":hits[:8],
            "limitations":[] if direct_metadata else ["Hipótese sem comprovação técnica; requer validação humana ou metadado operacional."]}
