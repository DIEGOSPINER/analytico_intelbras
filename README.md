# Analítico Intelbras

Videomonitoramento inteligente com YOLO + ByteTrack e análise comportamental com MediaPipe Pose.

## Funcionalidades

- Detecção e rastreamento de pessoas, veículos, animais e objetos
- Análise de ações (caminhar, correr, agachar, deitar, permanência, etc.)
- Eventos de risco (queda, aglomeração, possível briga, arma de fogo)
- Históricos em CSV para Power BI

## Configuração

1. Crie o ambiente virtual e instale as dependências:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Copie `cameras.example.json` para `cameras.json` e informe nome, IP, usuário e senha de cada câmera. Para incluir ou tirar uma câmera, edite essa lista: o analítico aplica a mudança sem reiniciar. `"ativa": false` pausa a câmera e mantém o cadastro.

3. Baixe/coloque os modelos na pasta do projeto:
   - `yolov8n.pt` (baixado automaticamente pelo Ultralytics na primeira execução, se ausente)
   - `pose_landmarker_lite.task`
   - `arma_fogo.pt` (opcional)

4. Execute:

```bash
python main.py
```

## Agente de análise

O agente lê os CSVs, alerta Face_ID, placas e ocorrências de atenção ou prioridade, e pede ao GPT um relatório por dia.

1. Crie uma chave em [platform.openai.com/api-keys](https://platform.openai.com/api-keys) e grave no `.env` como `OPENAI_API_KEY`. A chave começa com `sk-`. O modelo padrão é `gpt-6-sol`.
2. Copie `clientes.example.json` para `clientes.json`. Pessoas e veículos de interesse, câmeras e contatos de apoio ficam dentro da conta. `interesse.json` ainda é lido só na primeira criação dessa conta.
3. No `.env`, preencha `SMTP_SENHA` com uma senha de app do Gmail. O relatório diário sai às 21:00 para o e-mail, e o alerta de interesse ou de atenção sai na hora pelo mesmo e-mail. O WhatsApp fica desligado enquanto `WHATSAPP_ATIVO=0`.
4. Com o analítico aberto, a vigia roda junto. Fora dele:

```bash
python -m agente relatorio dia
python -m agente relatorio semana
python -m agente relatorio mes
python -m agente vigiar
```

Os relatórios em markdown ficam em `relatorios/`. O JSON do Power BI é um só, `relatorios/historico_relatorios.json`: cada dia entra como mais um registro na série, sem arquivo novo por data. As impressões também seguem em `historico_insights.csv` e os alertas em `historico_alertas_ia.csv`. A memória do que já foi observado na rua fica em `memoria_rua.json`.

## App iOS / Android

Pasta [`mobile/`](mobile/) — Expo espelhando o portal. YOLO continua no PC; o app usa `/api/mobile/login`, `/dados`, `/stive` e `/custos`. Instalação, EAS, TestFlight/Play e WhatsApp Meta: veja [`mobile/README.md`](mobile/README.md).

## Acesso na rede e pela internet

A análise **precisa** rodar no PC que enxerga as câmeras RTSP (`192.168.x.x`). Um VPS na nuvem sozinho não alcança essas câmeras. O navegador (celular, outro PC, fora de casa) entra no portal web deste PC.

### Passo a passo

1. **`.env`** — defina pelo menos:

```
WEB_SENHA=uma-senha-forte
WEB_HOST=0.0.0.0
WEB_PORT=8787
```

`WEB_SENHA` só cria o primeiro usuário. Depois cada pessoa entra com e-mail e senha próprios.

2. **Suba o analítico**

```bash
.\venv\Scripts\python.exe main.py
```

O console mostra as URLs. Exemplo na LAN: `http://192.168.0.3:8787/`.

3. **Mesma rede (celular / outro PC)**
   - Abra a URL da LAN no navegador.
   - Se não carregar, rode `.\abrir_tunel.ps1` uma vez (cria regra de firewall TCP 8787) ou libere a porta no Windows Defender Firewall.
   - Primeiro acesso: `/entrar` com e-mail, CPF/CNPJ e a `WEB_SENHA`.

4. **Fora da rede (internet)** — sem abrir porta no roteador:

```bash
winget install --id Cloudflare.cloudflared
.\abrir_tunel.ps1
```

Com o `main.py` ligado, o script imprime um `https://….trycloudflare.com`. Use esse endereço no celular 4G ou de outro lugar.  
Opcional no `.env` enquanto o túnel estiver ativo: `WEB_HTTPS=1` (cookie Secure).

5. **URL fixa (opcional)** — domínio na Cloudflare + túnel nomeado apontando para `http://127.0.0.1:8787`, depois `cloudflared tunnel run`.

6. **Só seus aparelhos (opcional)** — Tailscale: `winget install --id Tailscale.Tailscale`, mesma conta no celular, `tailscale serve 8787`.

### O que não fazer

- Não encaminhe no roteador a porta `554` (RTSP) nem a `8787` para a internet.
- Não desligue o PC que roda o `main.py` se quiser ver o portal ao vivo.
- Não compartilhe a URL `trycloudflare.com` publicamente: quem tiver o link ainda precisa do login, mas o endereço muda a cada execução do túnel rápido.

## Conta do cliente

O arquivo `clientes.json` (copie `clientes.example.json`) agrupa, por CPF ou CNPJ, os dados pessoais, as câmeras, as pessoas e os veículos de interesse e os e-mails e telefones de apoio. Cada conta só consulta e recebe os próprios alertas.

Uma pessoa de interesse só pode ser incluída com base legal: mandado judicial, medida protetiva ou acompanhamento de filhos e parentes, com a referência do processo, da medida ou do parentesco. No WhatsApp, depois de se identificar pelo CPF ou CNPJ, o cliente escolhe cadastrar veículo e motivo, pessoa e motivo, contatos ou uma ocorrência. A ocorrência guarda data, hora, natureza, descrição, latitude, longitude, endereço, placa, pessoa e a foto ou o vídeo. O agente liga a descrição ao que já existe na conta e nas câmeras e leva esses vínculos ao relatório. `fenomenos.json` só acumula contagens entre clientes, sem nome, placa, endereço ou documento. O aplicativo de consulta vem depois.

## Banco Postgres e nuvem (borda + API)

YOLO continua no PC do cliente. A nuvem guarda dados em Postgres.

```bash
# Schema: db/schema.sql
# Subir Postgres+API (com Docker):
cd nuvem
docker compose up -d --build

# Ou Postgres local já instalado:
.\db\preparar_local.ps1 -PostgresPassword "SENHA_DO_USUARIO_postgres" -ClienteDocumento "SEU_CPF"

# Migrar CSVs → banco:
.\venv\Scripts\python.exe -m db.migrar_csv --documento SEU_CPF

# Enviar da borda para a API:
.\venv\Scripts\python.exe -m borda.enviar_nuvem --url http://127.0.0.1:8080 --token SEU_TOKEN --documento SEU_CPF
```

Instalável no PC do cliente: `instalador\README_INSTALACAO.md` (`instalar.ps1`, `empacotar.ps1`).

## Arquivos de saída

- `historico_analitico.csv` — detecções
- `historico_ocorrencias.csv` — eventos comportamentais com classificação de risco
- `historico_ocorrencias_informadas.csv` — relatos feitos pelo cliente, com vínculos extraídos da descrição
- `historico_faces.csv` — cadastro/reaparecimento de faces próximas à câmera
- `historico_placas.csv` — leitura e reaparecimento de placas de veículos
- `historico_audio.csv` — transcrições e riscos de áudio
- `evidencias/faces/` e `evidencias/placas/` — screenshots de referência e passagens
- `db/schema.sql` — tabelas Postgres equivalentes
