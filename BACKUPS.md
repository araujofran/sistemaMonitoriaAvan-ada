# Política de backups e versões

Cada evolução funcional deve seguir esta sequência:

1. confirmar que testes e árvore Git estão limpos;
2. manter o tag da última versão como ponto de restauração;
3. implementar e testar a evolução;
4. atualizar `VERSION` e `CHANGELOG.md`;
5. criar commit da nova versão;
6. criar tag anotado (`v1.0.0`, `v1.1.0`, etc.);
7. enviar commit e tag ao GitHub.

## Restaurar sem apagar o trabalho atual

```powershell
git switch -c restauracao-v0 v0.0.0
```

Isso cria uma branch nova a partir do backup e não destrói alterações atuais.

## Backup dos dados analisados

Os tags Git protegem o código. Os dados operacionais do SQLite possuem backups separados em `backups/database/`, criados:

- manualmente pelo botão **Salvar backup agora**;
- automaticamente antes de reanalisar e sobrescrever duplicados;
- automaticamente antes de limpar toda a base;
- automaticamente antes de limpar um produto.

Os arquivos `.db` contêm dados de atendimentos e ficam ignorados pelo Git para não publicar CPF ou transcrições no repositório.

## Criar o próximo backup

```powershell
.\scripts\create_version.ps1 -Version "1.1.0" -Message "Descrição da versão"
git push origin main
git push origin "v1.1.0"
```
