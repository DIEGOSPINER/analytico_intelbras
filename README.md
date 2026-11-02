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

## Arquivos de saída

- `historico_analitico.csv` — detecções
- `historico_ocorrencias.csv` — eventos comportamentais com classificação de risco
- `historico_faces.csv` — cadastro/reaparecimento de faces próximas à câmera
- `historico_placas.csv` — leitura e reaparecimento de placas de veículos
- `evidencias/faces/` e `evidencias/placas/` — screenshots de referência e passagens
