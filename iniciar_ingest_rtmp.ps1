# Sobe o ingest RTMP (MediaMTX) para cameras remotas.
# Requisitos: mediamtx.exe no PATH ou em .\tools\mediamtx.exe
# Download: https://github.com/bluenviron/mediamtx/releases

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $raiz

$exe = $null
foreach ($candidato in @(
    (Join-Path $raiz "tools\mediamtx.exe"),
    (Join-Path $raiz "mediamtx.exe"),
    "mediamtx.exe",
    "mediamtx"
)) {
    if (Get-Command $candidato -ErrorAction SilentlyContinue) {
        $exe = (Get-Command $candidato).Source
        break
    }
    if (Test-Path $candidato) {
        $exe = (Resolve-Path $candidato).Path
        break
    }
}

if (-not $exe) {
    Write-Host "MediaMTX nao encontrado."
    Write-Host "1) Baixe o release Windows em https://github.com/bluenviron/mediamtx/releases"
    Write-Host "2) Coloque mediamtx.exe em .\tools\mediamtx.exe"
    Write-Host "3) Rode este script de novo."
    exit 1
}

$cfg = Join-Path $raiz "mediamtx.yml"
Write-Host "Ingest RTMP em :1935 | play RTSP em :8554"
Write-Host "Config: $cfg"
Write-Host "Defina RTMP_PUBLIC_HOST no .env com o IP/DNS publico desta maquina."
& $exe $cfg
