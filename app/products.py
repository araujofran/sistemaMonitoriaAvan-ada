from __future__ import annotations

import re
import unicodedata
from typing import Any


def plain(value: Any) -> str:
    text = "" if value is None else str(value)
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


PRODUCT_RULES: list[tuple[str, str]] = [
    (r"cart.?o\s+consignado", "Cart\u00e3o Consignado"),
    (r"cart.?o\s+(?:de\s+)?cr.?dito", "Cart\u00e3o de Cr\u00e9dito"),
    (r"ve.?culo|autom.?vel|financiamento\s+de\s+(?:carro|moto)", "Ve\u00edculos"),
    (r"empr.?stimo\s+consignado", "Empr\u00e9stimo Consignado"),
    (r"empr.?stimo", "Empr\u00e9stimo"),
    (r"financiamento", "Financiamento"),
    (r"conta\s+corrente", "Conta Corrente"),
    (r"renegocia..o", "Renegocia\u00e7\u00e3o"),
    (r"portabilidade", "Portabilidade"),
    (r"seguro", "Seguros"),
    (r"\bpix\b", "PIX"),
    (r"boleto", "Boleto"),
]

PRODUCT_KEYS = (
    "produto_cliente", "produto", "produto_final", "segmento", "carteira",
    "grupo_final", "grupo", "atendente", "tipo", "categoria_1", "categoria",
)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", plain(value)).strip("_")


def infer_product(metadata: dict[str, Any], transcript: str, fallback: str = "Não identificado") -> tuple[str, str]:
    normalized = {normalize_key(k): str(v) for k, v in metadata.items() if v not in (None, "")}
    ordered_values = [normalized[k] for k in PRODUCT_KEYS if k in normalized]
    search_space = ordered_values + [fallback, transcript[:8000]]
    for source in search_space:
        source_plain = plain(source)
        for pattern, canonical in PRODUCT_RULES:
            if re.search(plain(pattern), source_plain, re.I):
                origin = "metadata" if source in ordered_values else "transcri\u00e7\u00e3o"
                return canonical, origin
    raw = next((v.strip() for v in ordered_values if v.strip() and not v.strip().isdigit()), "")
    return (raw[:120], "metadata") if raw else (fallback, "motor regex")


def infer_attendant(metadata: dict[str, Any], fallback: str = "Não identificado") -> tuple[str, str]:
    normalized = {normalize_key(k): str(v).strip() for k, v in metadata.items() if v not in (None, "")}
    candidates = [normalized.get("atendente", ""), normalized.get("operador", ""), normalized.get("agente", ""), normalized.get("tipo", "")]
    product_words = {"veiculos", "cartao", "consignado", "sac", "cac", "credito", "emprestimo", "financiamento"}
    for value in candidates:
        words = set(plain(value).split())
        # A coluna explicitamente nomeada já fornece o contexto. Nomes simples,
        # matrículas e logins são identificadores válidos de operador.
        if value and not words.intersection(product_words) and not value.isdigit():
            return value, "metadata"
    return fallback, "análise"


ATTENDANT_PRESENTATION_PATTERNS = (
    re.compile(r"\b(?:eu\s+)?me chamo\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]{1,29})", re.I),
    re.compile(r"\bmeu nome\s+[eé]\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]{1,29})", re.I),
    re.compile(r"\bquem fala\s+[eé]\s+([A-ZÀ-Ý][A-Za-zÀ-ÿ'’-]{1,29})", re.I),
)


def extract_attendant_from_turns(turns: list[Any]) -> tuple[str, str]:
    """Extrai somente autoapresentação explícita do turno do atendente."""
    rejected = {"que", "uma", "com", "do", "da", "banco", "setor", "atendimento"}
    for turn in turns:
        speaker = turn.get("speaker") if isinstance(turn, dict) else getattr(turn, "speaker", "")
        text = turn.get("text_original", "") if isinstance(turn, dict) else getattr(turn, "text_original", "")
        if speaker != "ATENDENTE":
            continue
        for pattern in ATTENDANT_PRESENTATION_PATTERNS:
            match = pattern.search(str(text))
            if match and plain(match.group(1)) not in rejected:
                return match.group(1).strip().title(), match.group(0).strip()
    return "Não identificado", ""
