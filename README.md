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

## Conta do cliente

O arquivo `clientes.json` (copie `clientes.example.json`) agrupa, por CPF ou CNPJ, os dados pessoais, as câmeras, as pessoas e os veículos de interesse e os e-mails e telefones de apoio. Cada conta só consulta e recebe os próprios alertas.

Uma pessoa de interesse só pode ser incluída com base legal: mandado judicial, medida protetiva ou acompanhamento de filhos e parentes, com a referência do processo, da medida ou do parentesco. No WhatsApp, depois de se identificar pelo CPF ou CNPJ, o cliente escolhe cadastrar veículo e motivo, pessoa e motivo, contatos ou uma ocorrência. A ocorrência guarda data, hora, natureza, descrição, latitude, longitude, endereço, placa, pessoa e a foto ou o vídeo. O agente liga a descrição ao que já existe na conta e nas câmeras e leva esses vínculos ao relatório. `fenomenos.json` só acumula contagens entre clientes, sem nome, placa, endereço ou documento. O aplicativo de consulta vem depois.

## Arquivos de saída

- `historico_analitico.csv` — detecções
- `historico_ocorrencias.csv` — eventos comportamentais com classificação de risco
- `historico_ocorrencias_informadas.csv` — relatos feitos pelo cliente, com vínculos extraídos da descrição
- `historico_faces.csv` — cadastro/reaparecimento de faces próximas à câmera
- `historico_placas.csv` — leitura e reaparecimento de placas de veículos
- `evidencias/faces/` e `evidencias/placas/` — screenshots de referência e passagens
