# REGEX INTELLIGENCE — CX & Quality Analytics

Aplicação local para transformar transcrições bancárias em evidências auditáveis, critérios de monitoria, scores separados de operador/experiência e relatórios executivos de 14 blocos.

## Governança e isolamento por produto

O acesso exige autenticação e usa RBAC (`admin`, `gestao`, `especialista`). Cada produto possui um SQLite independente em `data/products/`; o banco só é selecionado após validar sessão e associação do usuário. Gestão é somente leitura, especialistas acessam apenas produtos associados e o administrador gerencia usuários, produtos e políticas oficiais em `/admin/governance`. Senhas são armazenadas somente como hashes PBKDF2.

Em uma instalação nova, defina as contas iniciais pelas variáveis listadas em `.env.example` antes da primeira inicialização. Nenhuma senha ou hash operacional é versionado. Em instalações existentes, os usuários do banco `data/governance.db` são preservados.

## Política de pontuação e explicabilidade

O administrador pode selecionar um, vários ou todos os produtos e aplicar a política rígida ou híbrida após visualizar o impacto. Cada produto mantém sua própria política. A ativação cria backup, atualiza a nota oficial, registra a nota anterior em `scoring_policy_history` e grava administrador, versão, operação e data. Novos atendimentos seguem automaticamente a política vigente.

A política híbrida não usa NLP como autoridade isolada: ausências de expressões Regex deixam de zerar automaticamente, enquanto evidências explícitas graves preservam o zeramento. O painel `/explainability` apresenta política ativa, notas, causas clicáveis, paginação, metadados, evidências e papel complementar do NLP.

Versão atual: **v1.2.0**. Consulte [CHANGELOG.md](CHANGELOG.md) e [BACKUPS.md](BACKUPS.md).

## Contrato implementado

| Grupo | Quantidade |
|---|---:|
| Relacionamento e Conduta | 14 |
| Resolutividade | 2 |
| CX | 9 |
| Inaderências | 7 |
| Ponto extra | 1 |
| CES | 3 |
| Fricção | 1 |
| Impactos e riscos | 5 |
| Causa raiz | 4 campos |
| Catálogo Regex | 100 detectores |

O validador impede que uma análise incompleta receba o status `VALID`. Cada evidência preserva detector, `regex_id`, speaker, trecho, posição, negação, confiança e critérios relacionados.

## Arquitetura

```text
TXT → parser de speakers → normalização → catálogo Regex
    → Evidence Engine → Rule Engine → critérios oficiais
    → validação de coerência → scores determinísticos
    → SQLite → FastAPI → Command Center / relatório de 14 blocos
```

## Instalação no Windows

1. Instale Python 3.11 ou superior.
2. Abra o PowerShell nesta pasta.
3. Execute:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py run.py
```

Abra `http://127.0.0.1:8765`. A documentação da API fica em `http://127.0.0.1:8765/docs`.

## Processar a pasta de exemplo

```powershell
py scripts/process_batch.py transcricoes --name "Lote exemplo"
```

## Arquivos aceitos

- Texto: `.txt`;
- delimitados: `.csv`, `.tsv`;
- Excel/planilhas: `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.ods`.

É possível combinar vários arquivos em um único upload. Para planilhas, todas as abas são lidas; cada linha que contenha transcrição vira um atendimento. A coluna pode se chamar `transcricao`, `texto`, `dialogo`, `conversa`, `atendimento` ou ser descoberta pelo conteúdo. Colunas adicionais, inclusive nomes ainda desconhecidos, são salvas integralmente como metadados sem exigir migração de schema.

Os dados são categorizados por produto normalizado, como `Cartão Consignado` ou `Veículos`, e podem ser consultados em `GET /api/v1/products`.

## Testes

```powershell
py -m pytest -q
```

## Endpoints principais

- `GET /health` — saúde e quantidade de detectores;
- `POST /api/v1/analyze` — análise avulsa sem persistência;
- `POST /api/v1/batches` — upload múltiplo e persistência;
- `GET /api/v1/batches/{id}` — visão executiva do lote;
- `GET /api/v1/interactions/{id}` — contrato estruturado integral;
- `GET /reports/{id}` — relatório visual individual;
- `GET /api/v1/regex` — Regex Lab/catálogo explicável;
- `GET /api/v1/journey` — funil causal e jornada agregada por lote/produto;
- `GET /monitoring` — painel completo de Monitoria 360°, preservando as telas existentes;
- `GET /explainability` — explicabilidade, comparação de políticas e rastreabilidade das inaderências;
- `POST /api/v1/admin/scoring-policy/preview` — prévia multi-produto sem alteração de notas;
- `POST /api/v1/admin/scoring-policy/apply` — aplica política oficial com backup e auditoria;
- `GET /api/v1/monitoring` — indicadores, operadores, riscos, causas e relatórios consolidados do banco;
- `GET /api/v1/monitoring/chat` — consulta conversacional rastreável sobre o recorte do painel;
- `GET /admin/diagnostics` — painel administrativo de saúde, banco e histórico de exceções;
- `POST /api/v1/uploads/preflight` — identifica atendimentos já analisados;
- `GET /api/v1/history/periods` — anos, meses e dias disponíveis;
- `GET /api/v1/history` — consulta histórica por período e produto;
- `POST /api/v1/admin/backups` — cria snapshot datado do SQLite;
- `DELETE /api/v1/admin/data` — limpeza confirmada total ou por produto;
- `GET /api/v1/interactions/{id}/export` — exportação JSON.

## Upload inteligente

Antes de processar, a aplicação calcula uma impressão digital do diálogo normalizado. Se o atendimento já existir, uma janela pergunta se o usuário quer reanalisar e sobrescrever ou ignorar os registros repetidos. Sobrescritas criam um backup automático do banco.

## Histórico e backups mensais

Cada análise recebe uma data local no formato `AAAA-MM-DD`. A tela permite filtrar por ano, mês, dia e produto. A área administrativa cria backups SQLite datados em `backups/database/`. Limpezas totais e por produto sempre criam um backup antes da exclusão.

## Jornada em lote

Abra `http://127.0.0.1:8765/journey` para visualizar o funil causal dos atendimentos. O painel diferencia causa raiz categorial de mecanismo técnico específico: quando a transcrição não comprova o mecanismo, ele é declarado como não determinado.

## Limites conscientes

O motor é determinístico e conservador. Ausência de expressão não comprova estado emocional, empatia ou causa técnica. Critérios acústicos como interrupção, paciência e calma ficam como `Não Aplicável` quando a transcrição não traz marcação temporal. Isso evita transformar hipótese em fato.
