param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
    [Parameter(Mandatory = $true)][string]$Message
)

$changes = git status --porcelain
if ($LASTEXITCODE -ne 0) { throw "Não foi possível consultar o Git." }
if ($changes) { throw "Existem alterações sem commit. Faça e valide o commit antes de criar a versão." }

$tag = "v$Version"
git rev-parse $tag 2>$null
if ($LASTEXITCODE -eq 0) { throw "A versão $tag já existe." }

git tag -a $tag -m $Message
if ($LASTEXITCODE -ne 0) { throw "Falha ao criar $tag." }
Write-Host "Backup $tag criado. Envie com: git push origin $tag"

