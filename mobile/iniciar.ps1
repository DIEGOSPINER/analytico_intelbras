# Garante Node no PATH desta sessão e sobe o Expo.
# Usa .cmd para nao depender do ExecutionPolicy do npm.ps1.
$nodeDir = "C:\Program Files\nodejs"
if (-not (Test-Path "$nodeDir\node.exe")) {
    Write-Host "Node.js nao encontrado em $nodeDir. Instale em https://nodejs.org/" -ForegroundColor Red
    exit 1
}
try {
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force -ErrorAction SilentlyContinue
} catch {}
$env:Path = "$nodeDir;" + $env:Path
Set-Location $PSScriptRoot
Write-Host "node: $(node -v)  npm: $(& "$nodeDir\npm.cmd" -v)" -ForegroundColor Cyan
if (-not (Test-Path "node_modules")) {
    Write-Host "Instalando dependencias..." -ForegroundColor Yellow
    & "$nodeDir\npm.cmd" install
}
& "$nodeDir\npx.cmd" expo start @args
