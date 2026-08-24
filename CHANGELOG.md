# Histórico de versões

## v1.2.0 — Upload inteligente, backups e histórico temporal

- Impressão digital global do conteúdo do atendimento, independente do nome do arquivo.
- Preflight de upload identifica atendimentos analisados antes do processamento.
- Modal com duas escolhas: reanalisar/sobrescrever ou ignorar duplicados.
- Backup automático do SQLite antes de sobrescritas e exclusões.
- Backup manual datado pela área administrativa.
- Limpeza completa da base ou somente de um produto, sempre com confirmação.
- Frase de confirmação obrigatória também na API administrativa.
- Data local da análise armazenada separadamente para histórico por ano, mês e dia.
- Consulta histórica combinando período e produto.
- Testes executados em bancos temporários isolados para preservar a base ativa.

## v1.1.0 — Jornada causal em lote

- Nova aba `Jornada em lote`, inspirada no dashboard Flowlu fornecido como referência.
- Funil de cinco níveis: voz do cliente, causa motivadora, fator da jornada, responsabilidade e causa raiz categorial.
- Extração rastreável da voz do cliente a partir das evidências existentes.
- Separação explícita entre causa categorial e mecanismo técnico comprovado.
- Cards executivos, ranking de causas, distribuição por produto e barras de responsabilidade.
- Filtros por lote e produto.
- Drill-down da trilha causal para o relatório individual.
- Endpoint agregado `GET /api/v1/journey`.

## v1.0.0 — Importação multiformato e produtos dinâmicos

- Upload simultâneo de um ou vários arquivos.
- Suporte a TXT, CSV, TSV, XLS, XLSX, XLSM, XLSB e ODS.
- Detecção de coluna de transcrição por alias ou conteúdo.
- Todas as colunas desconhecidas são preservadas como metadados dinâmicos.
- Cada linha de planilha vira um atendimento com arquivo, aba e linha de origem.
- Produtos são normalizados e exibidos em agrupamentos consultáveis.
- Índices e endpoints de produto no banco/API.

## v0.0.0 — Backup inicial

- Motor Regex, critérios oficiais, FastAPI, SQLite, relatórios e frontend iniciais.
- Snapshot imutável disponível pelo tag Git `v0.0.0`.
