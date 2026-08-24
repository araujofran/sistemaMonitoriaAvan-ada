# Mapa do contrato e matriz de implementação

## Cobertura oficial

| Grupo | Campos oficiais | Quantidade |
|---|---|---:|
| Relacionamento e Conduta | `at_rel_cord1..7`, `at_rel_ling1..5`, `at_rel_cond1..2` | 14 |
| Resolutividade | `at_resol_solic1..2` | 2 |
| CX | `at_cx_intro1..2`, `at_cx_compr1..4`, `at_cx_classif1..3` | 9 |
| Inaderências | `at_inad_compr1..7` | 7 |
| Pontos extras | `inv_extra1` | 1 |
| CES | `ces1_canal`, `ces2_retrabalho`, `ces3_reduziu` | 3 |
| Fricção | `cx1_friccao` | 1 |
| Impactos | `imp1_potencial_reclamacao..imp5_risco_reclamacao` | 5 |
| Causa raiz | `causaraiz1_descricao..causaraiz4_evidencia` | 4 |

## Matriz de implementação

| Campo/Critério | Regex | Rule Engine | Cálculo | Banco | Frontend |
|---|---|---|---|---|---|
| Relacionamento (14) | Sim | Sim | Peso × fator | Sim | Tabela integral |
| Resolutividade (2) | Sim | Sim | 10 pontos | Sim | Tabela integral |
| CX (9) | Sim | Sim | 40 pontos | Sim | Tabela integral |
| Inaderências (7) | Sim | Sim | -100 / zera | Sim | Bloco separado |
| Ponto extra (1) | Sim | Sim | +1, teto 100 | Sim | Nota/feedback |
| CES e Fricção | Sim | Sim | Score Experiência | JSON persistido | Bloco 8 |
| Impactos (5) | Sim | Sim | Penalidade de reclamação | JSON persistido | Bloco 9 |
| RCA (4) | Evidências operacionais | Sim, conservador | Não pontua | JSON persistido | Bloco 10 |
| Evidências | 100 detectores | Negação/contexto | Não pontua | Tabela própria | Regex Lab/API |

## Fórmulas

- Critérios: `nota = peso × fator`; Sim e Não Aplicável = 1, Parcial = 0,5, Não = 0.
- Score Operador: Relacionamento (50) + Resolutividade (10) + CX (40), aplicação de inaderência crítica e bônus, limitado a 0–100.
- Score Experiência: resolução (30) + ausência de reincidência (30) + esforço (0/10/20) + ausência de fricção (20) − reclamação alta (50), limitado a 0–100.

## Estrutura visual

O relatório preserva exatamente a sequência: Cabeçalho, Visão Geral, Feedback, Nota, Detalhamento, Inaderências, divisória de Inteligência, Diagnóstico, Esforço/Fricção, Riscos, RCA, Insights, Falhas, Plano de Ação e Conclusão.

