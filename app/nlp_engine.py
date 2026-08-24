from __future__ import annotations

from collections import Counter
import math
import re
import unicodedata
from typing import Any

NLP_VERSION = "hybrid-pt-1.0.0"
STOP = {"a","o","as","os","de","da","do","das","dos","e","em","um","uma","para","por","com","que","no","na","nos","nas","eu","voce","você","ele","ela","me","se","isso","esse","esta","está","ser","ter","foi","ao","à"}
TOPICS = {
    "Fraude e segurança": ("golpe","fraude","suspeita","pagamento liberar","boletim ocorrencia","senha","roubo"),
    "Prazo e acompanhamento": ("prazo","aguardar","dias uteis","retorno","acompanhamento","protocolo aberto"),
    "Remessa e câmbio": ("remessa","cambio","câmbio","mtcn","western union","cotacao","cotação","beneficiario"),
    "Cartões": ("cartao","cartão","fatura","limite","senha do cartao","compra"),
    "Cancelamento e estorno": ("cancelar","cancelamento","estorno","devolucao","devolução"),
    "Acesso e plataforma": ("aplicativo","app","site","sistema","indisponivel","erro","token","login"),
    "Reclamação": ("reclamacao","reclamação","ouvidoria","procon","bacen","insatisfeito","absurdo"),
}
POSITIVE = {"obrigado":1,"obrigada":1,"excelente":2,"otimo":2,"ótimo":2,"ajudou":1,"resolvido":2,"consegui":1,"alivio":2,"alívio":2,"perfeito":2}
NEGATIVE = {"problema":-1,"erro":-1,"absurdo":-3,"revoltado":-3,"revoltada":-3,"frustrado":-2,"frustrada":-2,"cansado":-2,"cansada":-2,"prejuizo":-3,"prejuízo":-3,"golpe":-3,"demora":-1,"nao resolveu":-3,"não resolveu":-3}


def _plain(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", text) if len(x.strip()) >= 8]


def _tokens(text: str) -> list[str]:
    return [x for x in re.findall(r"[a-zà-ÿ0-9]+", text.lower()) if len(x) > 2 and x not in STOP]


def _contains(plain_text: str, term: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(_plain(term)) + r"(?![a-z0-9])", plain_text))


def _sentiment(sentence: str) -> tuple[int, list[str]]:
    plain, score, evidence = _plain(sentence), 0, []
    for term, weight in {**POSITIVE, **NEGATIVE}.items():
        if _contains(plain, term):
            negated = bool(re.search(r"\b(?:nao|nunca|jamais)\b.{0,25}" + re.escape(_plain(term)), plain))
            score += -weight if negated else weight; evidence.append(term)
    return score, evidence


def _extractive_summary(sentences: list[str], limit: int = 3) -> list[str]:
    words = Counter(t for s in sentences for t in _tokens(s))
    ranked = sorted(enumerate(sentences), key=lambda x: sum(words[t] for t in _tokens(x[1])) / math.sqrt(max(1,len(_tokens(x[1])))), reverse=True)
    selected = sorted(ranked[:limit])
    return [s[:400] for _, s in selected]


def analyze_nlp(text: str, turns: list[Any] | None = None) -> dict[str, Any]:
    sentences = _sentences(text); plain = _plain(text)
    topic_scores = []
    for topic, terms in TOPICS.items():
        hits = [term for term in terms if _contains(plain, term)]
        if hits: topic_scores.append({"label":topic,"score":len(hits),"confidence":round(min(.97,.48+.12*len(hits)),2),"evidence":hits[:5]})
    topic_scores.sort(key=lambda x:x["score"], reverse=True)
    sentiment_points=[]
    for i,sentence in enumerate(sentences):
        score,evidence=_sentiment(sentence)
        if score: sentiment_points.append({"sentence":i+1,"score":score,"label":"Positivo" if score>0 else "Negativo","evidence":evidence,"text":sentence[:280]})
    total_sentiment=sum(x["score"] for x in sentiment_points)
    entities={
        "protocolos": sorted(set(re.findall(r"\b\d{8,20}\b", text)))[:20],
        "valores": sorted(set(re.findall(r"R\$\s*\d[\d.]*,?\d*", text, re.I)))[:20],
        "prazos": sorted(set(re.findall(r"\b(?:\d+|um|uma|dois|duas|tr[eê]s|cinco|sete|dez|quinze|trinta)\s+dias?(?:\s+[uú]teis)?\b", text, re.I)))[:20],
        "canais": [x for x in ("aplicativo","site","telefone","WhatsApp","agência","ouvidoria") if _contains(plain, x)],
    }
    transitions=[]
    if turns:
        for idx,turn in enumerate(turns):
            score,_=_sentiment(getattr(turn,"text_original",str(turn)))
            if score: transitions.append({"turn":idx+1,"speaker":getattr(turn,"speaker","ANY"),"score":score})
    confidence = round(min(.96,.42+.06*len(sentences)+.05*len(topic_scores)),2) if sentences else 0
    return {"version":NLP_VERSION,"provider":"local-contextual","language":"pt-BR","confidence":confidence,
            "topics":topic_scores[:5],"primary_topic":topic_scores[0]["label"] if topic_scores else "Não determinado",
            "sentiment":{"label":"Positivo" if total_sentiment>1 else "Negativo" if total_sentiment<0 else "Neutro","score":total_sentiment,"timeline":sentiment_points[:30]},
            "entities":entities,"summary":_extractive_summary(sentences),"emotional_transitions":transitions[:30],
            "audit":{"abstained":not bool(topic_scores),"method":"léxico contextual, negação, tópicos e sumarização extrativa"}}
