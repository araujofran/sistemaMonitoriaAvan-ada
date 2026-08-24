from __future__ import annotations

from html import escape

HYBRID_ZEROING_CODES = {"at_inad_compr4", "at_inad_compr6", "at_inad_compr7"}


def _zeroes_score(code: str, result: dict, policy: str) -> bool:
    if result.get("group") != "noncompliance" or result.get("classification") != "Sim":
        return False
    return policy != "hybrid" or code in HYBRID_ZEROING_CODES


def _noncompliance_effect(code: str, result: dict, policy: str) -> str:
    if result.get("classification") != "Sim":
        return "Sem efeito"
    if _zeroes_score(code, result, policy):
        return "Zera atendimento"
    return "Alerta/dedução — não zera"


def mask_cpf(value: str) -> str:
    digits = "".join(c for c in value if c.isdigit())
    return f"***.{digits[3:6]}.{digits[6:9]}-**" if len(digits) == 11 else "Não identificado"


def _table(rows: list[list], headers: list[str]) -> str:
    head = "".join(f"<th>{escape(str(x))}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(x))}</td>" for x in row) + "</tr>" for row in rows)
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _safe_metadata(metadata: dict) -> list[list[str]]:
    rows = []
    for key, value in metadata.items():
        label = str(key)
        shown = str(value)
        normalized = label.lower().replace("_", " ")
        if "cpf" in normalized:
            shown = mask_cpf(shown)
        elif any(token in normalized for token in ("telefone", "email", "endereco", "rg", "nome mae")):
            shown = "Dado pessoal preservado no banco e ocultado no relatório"
        rows.append([label, shown])
    return rows


def render_report(a: dict) -> str:
    scoring_policy = a.get("scoring_policy", {})
    active_policy = scoring_policy.get("policy", "rigid")
    policy_name = "Híbrida" if active_policy == "hybrid" else "Rígida"
    policy_version = scoring_policy.get("version", "rigid-1.0")
    c = a["criteria"]
    criteria_table = lambda group: _table([[code,r["name"],r["weight"],r["classification"],r["factor"],r["score"],"; ".join(r["evidence"]) or r["justification"]] for code,r in c.items() if r["group"]==group], ["Código","Critério","Peso","Resultado","Fator","Nota","Evidência"])
    noncomp = _table([[code,r["name"],r["classification"],_noncompliance_effect(code,r,active_policy),r["justification"]] for code,r in c.items() if r["group"]=="noncompliance"], ["Código","Critério","Resultado","Efeito na política vigente","Evidência"])
    ces = _table([[code,v["classificacao"],v["justificativa"]] for code,v in a["ces"].items()],["Código","Classificação","Justificativa"])
    risks = _table([[k,v["classificacao"],v["justificativa"]] for k,v in a["impacts"].items()],["Código","Classificação","Justificativa"])
    failed = [r for r in c.values() if r["group"] in {"relationship","resolution","cx"} and r["classification"] in {"Não","Parcial"}]
    positives = [r for r in c.values() if r["group"] in {"relationship","resolution","cx"} and r["classification"]=="Sim"]
    failures = [["Sondagem inadequada", int(c["at_cx_compr1"]["classification"]=="Não"), c["at_cx_compr1"]["justification"]], ["Próximos passos não informados",int(c["at_cx_classif2"]["classification"]=="Não"),c["at_cx_classif2"]["justification"]], ["Validação ou registro incompleto",int(c["at_cx_intro2"]["classification"] in {"Não","Parcial"}),c["at_cx_intro2"]["justification"]]]
    identified_noncompliance = any(r["classification"]=="Sim" for r in c.values() if r["group"]=="noncompliance")
    critical = any(_zeroes_score(code,r,active_policy) for code,r in c.items())
    rel=sum(r["score"] for r in c.values() if r["group"]=="relationship"); res=sum(r["score"] for r in c.values() if r["group"]=="resolution"); cx=sum(r["score"] for r in c.values() if r["group"]=="cx")
    metadata_rows = _safe_metadata(a.get("source_metadata", {}))
    source = a.get("source", {})
    source_html = (f"<details><summary>Metadados dinâmicos da origem</summary><p>Arquivo: {escape(str(source.get('filename', a['filename'])))} · Aba: {escape(str(source.get('sheet') or 'Não aplicável'))} · Linha: {escape(str(source.get('row') or 'Não aplicável'))}</p>{_table(metadata_rows,['Coluna original','Valor'])}</details>" if metadata_rows else "")
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>Monitoria — {escape(a['filename'])}</title><link rel='stylesheet' href='/static/style.css'><link rel='stylesheet' href='/static/report-fixes.css'></head><body><main><nav class='report-context-nav'><a href='/'>Início</a><a href='/monitoring'>Monitoria 360°</a><a href='/journey'>Jornada</a><a href='javascript:history.back()'>Voltar ao painel de origem</a></nav>
<section><p class='eyebrow dark'>1. CABEÇALHO DO ATENDIMENTO</p><h1>MONITORIA DE QUALIDADE</h1>{_table([[a['data_interacao'][:10],a['protocolo'],a['nome_cliente'],mask_cpf(a['cpf']),a['atendente'],a['produto_principal'],a['motivo_contato'],'Telefone']],['Data','Protocolo','Cliente','CPF','Atendente','Produto','Categoria','Canal'])}<div class='score'><small>NOTA FINAL DA MONITORIA</small><strong>{a['score_operador']} / 100</strong><span>{a['classificacao_operador']}</span></div><p><b>Política oficial de pontuação:</b> {policy_name} · versão {escape(str(policy_version))}</p>{source_html}</section>
<section><h2>2. VISÃO GERAL DA MONITORIA</h2><h3>{'🔴 ALERTA CRÍTICO' if critical else '🟡 PONTO DE ATENÇÃO' if a['score_operador'] < 85 else '🟢 CASO CONTROLADO'}</h3><p>{escape(a['resumo'])} A classificação decorre exclusivamente dos critérios e evidências exibidos abaixo.</p></section>
<section><h2>3. FEEDBACK DA MONITORIA</h2><h3>✅ Pontos Positivos</h3><p>{escape('; '.join(r['name'] for r in positives) or 'Nenhum ponto positivo comprovado.')}</p><h3>⚠️ Pontos de Melhoria</h3><p>{escape('; '.join(r['name'] for r in failed) or 'Não foram identificadas oportunidades relevantes de melhoria para o operador neste atendimento.')}</p><h3>🎓 Coaching Sugerido</h3><p>Confirmar o entendimento, esclarecer próximos passos e registrar evidências de conclusão antes do encerramento.</p></section>
<section><h2>4. NOTA DA MONITORIA</h2>{_table([['Relacionamento e Conduta',50,rel],['Resolutividade',10,res],['CX',40,cx],['Inaderências',f'Política {policy_name}','Zera' if critical else 'Não zera'],['Pontos Extras','Bônus',c['inv_extra1']['bonus']]],['Pilar','Regra/Peso máximo','Resultado'])}<h3>NOTA FINAL: {a['score_operador']}/100 — {a['classificacao_operador']}</h3></section>
<section><h2>5. DETALHAMENTO DA MONITORIA</h2><h3>🤝 Relacionamento e Conduta — {rel}/50</h3>{criteria_table('relationship')}<h3>🎯 Resolutividade — {res}/10</h3>{criteria_table('resolution')}<h3>💙 CX — {cx}/40</h3>{criteria_table('cx')}</section>
<section><h2>6. 🚨 INADERÊNCIAS E EFEITOS</h2><p>{'🚨 Inaderência zeradora identificada na política vigente.' if critical else '⚠️ Inaderências identificadas como alerta/dedução; nenhuma delas zera este atendimento na política híbrida.' if identified_noncompliance else '✅ Nenhuma inaderência identificada.'}</p>{noncomp}</section>
<div class='divider'><h1>INTELIGÊNCIA DE CX E QUALIDADE</h1></div>
<section><h2>7. DIAGNÓSTICO DA EXPERIÊNCIA</h2><div class='cards'><article><small>Score Experiência</small><strong>{a['score_experiencia']}/100</strong></article><article><small>Resolutivo</small><strong>{a['atendimento_resolutivo']['classificacao']}</strong></article><article><small>Esforço</small><strong>{a['nivel_esforco_cliente']['classificacao']}</strong></article><article><small>Recontato</small><strong>{a['probabilidade_recontato']['classificacao']}</strong></article></div><p>Humor do cliente: {a['humor_cliente']['classificacao']}. Responsabilidade: {a['responsabilidade']}.</p></section>
<section><h2>8. ESFORÇO E FRICÇÃO DA JORNADA</h2>{ces}<p><b>Fricção:</b> {a['cx1_friccao']['classificacao']} — {escape(a['cx1_friccao']['justificativa'])}</p></section>
<section><h2>9. RISCOS E IMPACTOS</h2>{risks}</section>
<section><h2>10. CAUSA RAIZ E RESPONSABILIDADE</h2>{_table([[k,v] for k,v in a['root_cause'].items()],['Campo','Resultado'])}<p><b>Responsabilidade:</b> {a['responsabilidade']} — {escape(a['responsabilidade_motivo'])}</p></section>
<section><h2>11. INSIGHTS DA INTERAÇÃO</h2><h3>💡 Insight Operacional</h3><p>Orientação completa e validação do entendimento podem reduzir novo contato.</p><h3>💙 Apontamento de CX</h3><p>{escape('; '.join(r['name'] for r in failed if r['group']=='cx') or 'Nenhum apontamento negativo.')}</p><h3>🎯 Apontamento de Resolutividade</h3><p>{escape('; '.join(r['name'] for r in failed if r['group']=='resolution') or 'Nenhum apontamento negativo.')}</p><h3>👤 Oportunidade do Operador</h3><p>{escape('; '.join(r['name'] for r in failed) or 'Não foram identificadas oportunidades relevantes de melhoria para o operador neste atendimento.')}</p></section>
<section><h2>12. FALHAS OPERACIONAIS IDENTIFICADAS</h2>{_table(failures,['Falha operacional','Ocorrências','Evidência'])}</section>
<section><h2>13. RECOMENDAÇÕES E PLANO DE AÇÃO</h2>{_table([['Alta','Reforçar confirmação de dados e entendimento','Operação','Curto prazo','Maior rastreabilidade'],['Média','Padronizar próximos passos no encerramento','Processo','Médio prazo','Redução de retrabalho']],['Prioridade','Ação','Responsável sugerido','Prazo sugerido','Impacto esperado'])}</section>
<section><h2>14. 📌 CONCLUSÃO EXECUTIVA</h2><p>O caso apresenta desempenho {escape(a['classificacao_operador'].lower())}, experiência de {a['score_experiencia']}/100 e motivo principal “{escape(a['motivo_contato'])}”. A prioridade é tratar os critérios negativos comprovados, preservando a separação entre conduta do operador e fatores externos.</p></section>
</main><script src='/static/governance-client.js'></script></body></html>"""
