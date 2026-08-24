# ADR-001 — Funil causal em modo shadow

- Data: 2026-08-24
- Estado: aceita

## Contexto

O painel de jornada apresentava repetidamente “mecanismo técnico não determinado”. A classificação temática existente não encadeava voz, motivo, jornada, atrito e causa candidata.

## Decisão

Introduzir um motor causal explicável e persistido, inicialmente em modo shadow. O painel apresenta evidência, etapa, causa candidata, status e confiança. Nenhuma nota é modificada.

## Consequências

Ganho: explicações mais específicas e rastreáveis. Custo: nova tabela, processamento adicional e necessidade de evolução da taxonomia. Risco: usuário interpretar hipótese como fato; mitigação: rótulo explícito, confiança, limitações e abstenção.

## Validação

Testes unitários verificam hipótese rastreável, abstenção sem evidência e persistência separada. A validação de negócio deve comparar as sugestões com casos revisados por especialistas.
