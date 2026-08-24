# Manual das técnicas aplicadas

## 1. Regex e regras determinísticas

Local principal: `app/catalog.py`, `app/evidence_engine.py` e `app/rule_engine.py`.

Usamos expressões regulares quando a decisão depende de uma manifestação textual objetiva: protocolo, saudação, confirmação, encerramento, termos de risco e demais critérios catalogados. Regex é previsível, auditável e reproduzível, mas a ausência de uma expressão não prova, sozinha, que uma conduta não aconteceu.

## 2. Motor de evidências

O motor liga cada ocorrência ao turno, interlocutor, posição no texto, negação, critério e nível de confiança. Ele existe para impedir conclusões sem rastreamento até a fonte.

## 3. NLP contextual local

Local: `app/nlp_engine.py`. Versão atual: `hybrid-pt-1.0.0`.

Aplica normalização linguística, tópicos por léxico contextual, tratamento básico de negação, sentimento, entidades, resumo extrativo e transições emocionais. Seu papel é complementar o Regex. Não possui autoridade isolada para alterar nota ou declarar uma causa técnica.

## 4. Funil causal explicável

Local: `app/causal_engine.py`. Versão inicial: `causal-shadow-1.0.0`.

Transforma evidências do cliente em: voz, problema expresso, etapa da jornada, atrito, responsável, causa candidata, confiança e status. A primeira versão usa taxonomia causal explícita e sinais linguísticos verificáveis. Ela se abstém quando não há sustentação suficiente.

Estados possíveis: `Causa comprovada`, `Hipótese causal forte`, `Hipótese causal fraca` e `Não determinada`. Sem metadado técnico ou operacional, uma conclusão permanece hipótese.

## 5. Política de score

As políticas rígida e híbrida são versionadas e mantêm histórico. O funil causal está em modo shadow e não participa do cálculo. Qualquer promoção futura exige nova decisão arquitetural, simulação, aprovação e trilha de auditoria.

## 6. Persistência e isolamento por produto

Cada produto usa seu banco isolado. NLP é persistido em `nlp_results`; o funil, em `causal_analysis_results`; futuras revisões humanas ficam em `causal_analysis_reviews`. O JSON consolidado da interação também recebe `causal_funnel`, garantindo exportação e leitura do relatório.

## 7. Governança

Admin possui ações administrativas; Gestão consulta produtos autorizados; Especialista acessa apenas seus produtos. A análise causal respeita o mesmo escopo de banco definido pelo middleware de governança.

## 8. Evolução planejada

Embeddings, busca semântica, NLI, reranqueamento e modelos supervisionados só deverão entrar quando houver base validada, medição de precisão e decisão arquitetural própria. Uma biblioteca nova não transforma hipótese em fato; a evidência e a revisão continuam obrigatórias.

## 9. Monitoria 360°, rastreabilidade e metas

O painel devolve todos os atendimentos do recorte para permitir busca, filtro de risco e exportação rastreável. Riscos multivalorados são normalizados como categorias individuais, nunca apresentados como representação interna de lista.

Operador monitorado e usuário que enviou o lote são identidades distintas. O primeiro vem exclusivamente de coluna `ATENDENTE`, `OPERADOR` ou `AGENTE`; o segundo passa a ser registrado em `analysis_batches.uploaded_by`. Quando a fonte histórica não contém operador, o painel informa a cobertura em vez de inventar uma atribuição.

As metas são propostas sobre a linha de base filtrada: +8 pontos no Score Operador, +10 em Experiência, +15 pontos percentuais de resolução e redução de 30% dos alertas críticos, sempre respeitando os limites válidos. Elas orientam o próximo ciclo, mas não alteram resultados históricos.
