# Cria usuário/banco c4istar no Postgres local e aplica schema + carga CSV.
# Uso:
#   .\db\preparar_local.ps1 -PostgresPassword "senha_do_superuser"
#   .\db\preparar_local.ps1 -PostgresPassword "..." -ClienteDocumento "02401001581"

param(
  [Parameter(Mandatory = $true)][string]$PostgresPassword,
  [string]$ClienteDocumento = "",
  [string]$PgBin = ""
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path $PSScriptRoot -Parent
Set-Location $raiz

if (-not $PgBin) {
  foreach ($v in @("18", "16", "15", "14")) {
    $c = "C:\Program Files\PostgreSQL\$v\bin\psql.exe"
    if (Test-Path $c) { $PgBin = Split-Path $c -Parent; break }
  }
}
if (-not $PgBin) { throw "PostgreSQL não encontrado em Program Files." }

$psql = Join-Path $PgBin "psql.exe"
$env:PGPASSWORD = $PostgresPassword

Write-Host "Criando role/banco c4istar..."
& $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'c4istar') THEN CREATE ROLE c4istar LOGIN PASSWORD 'c4istar'; END IF; END `$`$;"
& $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c "SELECT 'ok' FROM pg_database WHERE datname='c4istar'" | Out-Null
$dbExists = & $psql -U postgres -h 127.0.0.1 -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='c4istar'"
if (-not $dbExists.Trim()) {
  & $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE c4istar OWNER c4istar;"
}
& $psql -U postgres -h 127.0.0.1 -d postgres -v ON_ERROR_STOP=1 -c "GRANT ALL PRIVILEGES ON DATABASE c4istar TO c4istar;"

$url = "postgresql://c4istar:c4istar@127.0.0.1:5432/c4istar"
$env:DATABASE_URL = $url

# Garante linhas no .env
$envFile = Join-Path $raiz ".env"
if (Test-Path $envFile) {
  $txt = Get-Content $envFile -Raw
  if ($txt -notmatch '(?m)^\s*DATABASE_URL\s*=') {
    Add-Content $envFile "`nDATABASE_URL=$url"
  }
}

Write-Host "Aplicando schema e migrando CSVs..."
& .\venv\Scripts\python.exe -c "from db.conexao import aplicar_schema; aplicar_schema(); print('schema ok')"
$docArg = @()
if ($ClienteDocumento) { $docArg = @("--documento", $ClienteDocumento) }
& .\venv\Scripts\python.exe -m db.migrar_csv @docArg
Write-Host "Pronto. DATABASE_URL=$url" -ForegroundColor Green
