# Abre o C4ISTAR MONITOR na internet via túnel Cloudflare (sem abrir porta no roteador).
# Pré-requisito: main.py rodando com WEB_SENHA no .env.

$ErrorActionPreference = "Stop"
$porta = 8787
if (Test-Path .env) {
  $linha = Select-String -Path .env -Pattern '^\s*WEB_PORT\s*=' | Select-Object -First 1
  if ($linha) {
    $valor = ($linha.Line -split '=', 2)[1].Trim().Trim('"').Trim("'")
    if ($valor -match '^\d+$') { $porta = [int]$valor }
  }
}

Write-Host "=== C4ISTAR · acesso remoto ===" -ForegroundColor Cyan

# Libera a porta na firewall do Windows (rede local).
$regra = "C4ISTAR MONITOR $porta"
$existe = Get-NetFirewallRule -DisplayName $regra -ErrorAction SilentlyContinue
if (-not $existe) {
  try {
    New-NetFirewallRule -DisplayName $regra -Direction Inbound -Protocol TCP -LocalPort $porta -Action Allow | Out-Null
    Write-Host "Firewall: regra criada para TCP $porta (entrada)."
  } catch {
    Write-Host "Firewall: não consegui criar a regra automaticamente. Libere TCP $porta manualmente."
  }
} else {
  Write-Host "Firewall: regra '$regra' já existe."
}

$ips = Get-NetIPAddress -AddressFamily IPv4 |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Select-Object -ExpandProperty IPAddress
Write-Host "Na mesma rede, abra:"
foreach ($ip in $ips) {
  Write-Host "  http://${ip}:${porta}/"
}
Write-Host "Neste PC: http://127.0.0.1:${porta}/"

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
  Write-Host ""
  Write-Host "cloudflared não encontrado. Instale com:"
  Write-Host "  winget install --id Cloudflare.cloudflared"
  Write-Host "Depois rode este script de novo."
  exit 1
}

Write-Host ""
Write-Host "Subindo túnel público HTTPS → http://127.0.0.1:$porta"
Write-Host "Copie a URL https://....trycloudflare.com que aparecer abaixo."
Write-Host "Dica: no .env use WEB_HTTPS=1 enquanto o túnel estiver ativo."
Write-Host "Ctrl+C encerra só o túnel (o main.py continua)."
Write-Host ""

& cloudflared tunnel --url "http://127.0.0.1:$porta"
