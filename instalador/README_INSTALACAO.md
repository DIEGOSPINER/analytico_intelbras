# Instalação no computador do cliente (borda)

O YOLO, as câmeras RTSP e o portal local rodam **neste PC**. A nuvem (Postgres + API) só recebe os dados.

## Requisitos

- Windows 10/11
- Python 3.10+ (`winget install Python.Python.3.12`)
- ffmpeg no PATH (áudio)
- Câmeras Intelbras acessíveis na rede local

## Instalação rápida

1. Copie a pasta do pacote (ou o zip `C4ISTAR-borda.zip`) para o PC.
2. PowerShell:

```powershell
cd C:\caminho\do\pacote
Set-ExecutionPolicy -Scope Process Bypass
.\instalador\instalar.ps1 -PastaDestino C:\C4ISTAR
```

3. Edite `C:\C4ISTAR\.env`:
   - `WEB_SENHA=...`
   - `WEB_HOST=0.0.0.0`
   - `CLIENTE_DOCUMENTO=` CPF/CNPJ do cliente
   - Opcional nuvem: `NUVEM_API_URL=https://sua-api` e `INGEST_TOKEN=...`
4. Edite `C:\C4ISTAR\cameras.json`.
5. Inicie pelo atalho **C4ISTAR MONITOR** ou `iniciar.bat`.
6. Portal local: `http://127.0.0.1:8787/` (ou IP da máquina na LAN).

## Enviar dados para a nuvem

Com a API no ar:

```powershell
cd C:\C4ISTAR
.\venv\Scripts\python.exe -m borda.enviar_nuvem --url https://sua-api --token SEU_TOKEN --documento 00000000000
```

## Desinstalação

Apague `C:\C4ISTAR` e o atalho da área de trabalho.
