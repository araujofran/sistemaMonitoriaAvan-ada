from __future__ import annotations

from collections import Counter
from .criteria import GROUP_COUNTS


class ContractError(ValueError):
    pass


def validate_analysis(analysis: dict) -> list[str]:
    errors: list[str] = []
    criteria = analysis.get("criteria", {})
    counts = Counter(v.get("group") for v in criteria.values())
    for group, expected in GROUP_COUNTS.items():
        if counts[group] != expected:
            errors.append(f"{group}: esperado {expected}, encontrado {counts[group]}")
    if len(analysis.get("ces", {})) != 3:
        errors.append("CES: esperado 3")
    if "cx1_friccao" not in analysis:
        errors.append("Fricção ausente")
    if len(analysis.get("impacts", {})) != 5:
        errors.append("Impactos: esperado 5")
    if len(analysis.get("root_cause", {})) != 4:
        errors.append("Causa raiz: esperado 4")
    required = {"score_operador","score_experiencia","classificacao_operador","atendimento_resolutivo","nivel_esforco_cliente","probabilidade_recontato"}
    errors.extend(f"Campo ausente: {field}" for field in sorted(required - analysis.keys()))
    for code, item in criteria.items():
        if item.get("classification") not in {"Sim","Não","Parcial","Não Aplicável"}:
            errors.append(f"{code}: classificação inválida")
        expected = round(float(item.get("weight", 0)) * float(item.get("factor", 0)), 2)
        if round(float(item.get("score", 0)), 2) != expected:
            errors.append(f"{code}: nota incompatível")
    analysis["analysis_status"] = "VALID" if not errors else "INVALID_CONTRACT"
    analysis["contract_errors"] = errors
    return errors


def assert_valid(analysis: dict) -> None:
    errors = validate_analysis(analysis)
    if errors:
        raise ContractError("; ".join(errors))

