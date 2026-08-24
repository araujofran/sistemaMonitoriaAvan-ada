# Funil inteligente de compreensão

## Objetivo

Responder, para cada atendimento: o que o cliente disse; por que disse; em qual etapa da jornada ocorreu; qual atrito foi observado; qual causa raiz é candidata; e quão sustentada é a conclusão.

## Fluxo

`Voz → problema expresso → etapa da jornada → atrito → responsabilidade → causa candidata → confiança/status`

## Contrato salvo

- `version`: versão reprodutível do motor.
- `mode`: `shadow` enquanto não afetar decisões oficiais.
- `voice`: trecho ou evidência principal.
- `expressed_problem`: categoria do problema manifestado.
- `journey_stage`: estágio identificado.
- `friction`: atrito observado.
- `root_candidate`: causa sugerida, nunca apresentada como fato sem comprovação.
- `responsibility`: dono categorial disponível.
- `confidence`: força da sustentação, de 0 a 1.
- `status`: classificação de governança.
- `evidence`: trechos rastreáveis.
- `limitations`: alertas que o usuário precisa conhecer.

## Persistência e retroprocessamento

Novos atendimentos são persistidos automaticamente. Para registros existentes, o endpoint administrativo `POST /api/v1/admin/causal/enrich` recalcula e salva o funil no banco ativo do produto. O processo não altera nota.

## Limite epistemológico

Texto não revela necessariamente o componente técnico que falhou. Sem incidente, log, código de erro, evento de jornada ou validação humana, a saída correta é uma hipótese ou abstenção. O sistema não deve fabricar precisão.
