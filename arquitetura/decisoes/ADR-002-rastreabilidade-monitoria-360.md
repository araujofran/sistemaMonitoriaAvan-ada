# ADR-002 — Rastreabilidade e metas da Monitoria 360°

- Data: 2026-08-24
- Estado: aceita

## Contexto

O painel agregava 1.065 registros, mas retornava apenas 500 linhas detalhadas; riscos multivalorados apareciam como listas Python e a ausência de coluna de operador era apresentada sem diagnóstico de qualidade. Os relatórios recomendavam evolução sem linha de base ou meta numérica.

## Decisão

Entregar toda a lista do recorte, filtros locais de risco, busca, exportação CSV, categorias regulatórias normalizadas, cobertura de identificação de operador e metas calculadas a partir da linha de base. Registrar o usuário que realizou novos uploads separadamente do operador monitorado.

## Consequências

A rastreabilidade passa a cobrir todo o recorte. Respostas maiores exigem mais tráfego no navegador; paginação de servidor será considerada caso a volumetria cresça significativamente. Dados históricos sem operador ou usuário de upload continuam explicitamente ausentes, pois não serão fabricados.
