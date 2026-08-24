# Arquitetura e decisões técnicas

Esta pasta é o manual técnico cumulativo do sistema. Ela deve crescer junto com o produto.

## Regra de manutenção

- Não apagar decisões anteriores para esconder mudanças de direção.
- Adicionar uma decisão em `decisoes/` para toda alteração relevante de arquitetura, modelo, banco ou regra de negócio.
- Atualizar o manual da técnica afetada e o índice abaixo.
- Registrar versão, data, motivação, impacto, limitações e como validar.
- Técnicas substituídas permanecem documentadas e recebem o estado `substituída` e um link para a decisão sucessora.

## Índice

| Documento | Conteúdo |
|---|---|
| [Manual de técnicas](manual-tecnicas.md) | Regex, evidência, NLP, causa, score, governança e persistência |
| [Funil causal](funil-causal.md) | Funcionamento, contrato, limites e validação do modo shadow |
| [ADR-001](decisoes/ADR-001-funil-causal-shadow.md) | Decisão de introduzir a análise causal sem alterar notas |
| [ADR-002](decisoes/ADR-002-rastreabilidade-monitoria-360.md) | Rastreabilidade, riscos normalizados, auditoria de upload e metas |
| [ADR-003](decisoes/ADR-003-migracoes-automaticas-por-produto.md) | Migrações automáticas, idempotentes e isoladas por produto |
| [Histórico](HISTORICO.md) | Registro cumulativo das mudanças de arquitetura |

## Fluxo para novos ajustes

1. Criar ou atualizar testes.
2. Implementar com versão explícita.
3. Criar uma ADR em `decisoes/ADR-NNN-titulo.md`.
4. Atualizar `manual-tecnicas.md` sem remover o contexto anterior.
5. Acrescentar uma linha em `HISTORICO.md`.
