# Gera pasta/zip para levar ao cliente e instalar offline-ish.
# Uso: .\instalador\empacotar.ps1

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
$saida = Join-Path $raiz "dist\C4ISTAR-borda"
Remove-Item $saida -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $saida | Out-Null

& (Join-Path $PSScriptRoot "instalar.ps1") -PastaDestino $saida -Origem $raiz

# Não levar venv gigante no zip se quiser — recria no cliente:
Remove-Item (Join-Path $saida "venv") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $saida ".env") -Force -ErrorAction SilentlyContinue

$zip = Join-Path $raiz "dist\C4ISTAR-borda.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $saida "*") -DestinationPath $zip -Force
Write-Host "Pacote: $zip"
Write-Host "No cliente: extrair, rodar instalador\instalar.ps1 -PastaDestino C:\C4ISTAR -Origem <pasta_extraida>"
# Ajuste: copiar scripts do instalador para dentro do pacote
Copy-Item (Join-Path $PSScriptRoot "*") (Join-Path $saida "instalador") -Recurse -Force
Compress-Archive -Path (Join-Path $saida "*") -DestinationPath $zip -Force
Write-Host "Atualizado: $zip"
