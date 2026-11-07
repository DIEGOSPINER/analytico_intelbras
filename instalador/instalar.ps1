# Instalação do C4ISTAR MONITOR no PC do cliente (borda).
# Uso (PowerShell como Administrador recomendado):
#   .\instalador\instalar.ps1
#   .\instalador\instalar.ps1 -PastaDestino "C:\C4ISTAR"

param(
  [string]$PastaDestino = "C:\C4ISTAR",
  [string]$Origem = ""
)

$ErrorActionPreference = "Stop"

if (-not $Origem) {
  $Origem = Split-Path $PSScriptRoot -Parent
}

Write-Host "=== C4ISTAR MONITOR · instalação na borda ===" -ForegroundColor Cyan
Write-Host "Origem:  $Origem"
Write-Host "Destino: $PastaDestino"

if (-not (Test-Path (Join-Path $Origem "main.py"))) {
  throw "main.py não encontrado em $Origem"
}

New-Item -ItemType Directory -Force -Path $PastaDestino | Out-Null

$incluir = @(
  "main.py", "remoto.py", "painel_web.js", "audio.py", "audio_registro.py",
  "rota_vias.py", "folium_mapa.py", "acesso.py", "cadastro.py", "cameras.py",
  "identidade.py", "ocorrencias.py", "painel.py", "monitores.py", "mapa.py",
  "requirements.txt", "cameras.example.json", "clientes.example.json",
  ".env.example", "abrir_tunel.ps1", "README.md"
)
$pastas = @("agente", "db", "borda", "assets")

foreach ($arq in $incluir) {
  $src = Join-Path $Origem $arq
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $PastaDestino $arq) -Force
  }
}
foreach ($dir in $pastas) {
  $src = Join-Path $Origem $dir
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $PastaDestino $dir) -Recurse -Force
  }
}

# Modelos e evidências (se existirem)
foreach ($extra in @("yolov8n.pt", "pose_landmarker_lite.task", "arma_fogo.pt", "evidencias")) {
  $src = Join-Path $Origem $extra
  if (Test-Path $src) {
    Copy-Item $src (Join-Path $PastaDestino $extra) -Recurse -Force
  }
}

Set-Location $PastaDestino

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env" -Force
  Write-Host "Criei .env a partir do exemplo. Edite WEB_SENHA e câmeras."
}
if (-not (Test-Path "cameras.json") -and (Test-Path "cameras.example.json")) {
  Copy-Item "cameras.example.json" "cameras.json" -Force
}
if (-not (Test-Path "clientes.json") -and (Test-Path "clientes.example.json")) {
  Copy-Item "clientes.example.json" "clientes.json" -Force
}

Write-Host "Criando venv e instalando dependências..."
if (-not (Test-Path "venv")) {
  py -3 -m venv venv
  if ($LASTEXITCODE -ne 0) { python -m venv venv }
}
& .\venv\Scripts\python.exe -m pip install --upgrade pip
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe -m pip install "psycopg[binary]" fastapi uvicorn

Copy-Item (Join-Path $PSScriptRoot "iniciar.bat") (Join-Path $PastaDestino "iniciar.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "README_INSTALACAO.md") (Join-Path $PastaDestino "README_INSTALACAO.md") -Force

$atalho = Join-Path ([Environment]::GetFolderPath("Desktop")) "C4ISTAR MONITOR.lnk"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($atalho)
$lnk.TargetPath = Join-Path $PastaDestino "iniciar.bat"
$lnk.WorkingDirectory = $PastaDestino
$lnk.Description = "C4ISTAR MONITOR"
$lnk.Save()

Write-Host ""
Write-Host "Instalação concluída em $PastaDestino" -ForegroundColor Green
Write-Host "1) Edite .env (WEB_SENHA) e cameras.json"
Write-Host "2) Clique no atalho da área de trabalho ou rode iniciar.bat"
Write-Host "3) Opcional nuvem: NUVEM_API_URL e INGEST_TOKEN no .env"
