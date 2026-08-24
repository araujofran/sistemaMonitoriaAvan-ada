# ADR-003 — Migrações automáticas de dados por produto

- Data: 2026-08-24
- Estado: aceita

## Contexto

O enriquecimento retroativo de operadores foi executado manualmente como correção emergencial. Esse procedimento depende de intervenção técnica e não atende ao requisito de autonomia do sistema.

## Decisão

Cada banco de produto mantém a tabela `data_migrations`. Na inicialização, depois da preparação dos bancos e da migração legada, o sistema verifica versões pendentes, cria backup quando há registros afetados, executa o enriquecimento e grava resultado, versão, data e nome do backup. A mesma versão nunca é reaplicada.

Novos atendimentos não dependem da migração: o operador é extraído e persistido durante o processamento normal. Novos produtos também recebem imediatamente o controle de versões.

## Consequências

O sistema passa a evoluir dados históricos sem intervenção manual, preservando isolamento por produto e auditoria. A primeira inicialização após uma nova migração pode demorar mais devido ao backup e ao processamento; execuções seguintes apenas consultam a versão registrada.
