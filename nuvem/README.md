# Nuvem C4ISTAR (Lightsail / ECS)

Postgres + API de ingestão. A análise YOLO fica no PC do cliente (borda).

## Local / Lightsail

```bash
cd nuvem
copy .env.example .env
docker compose up -d --build
```

API: `http://127.0.0.1:8080/saude`  
Ingestão: `POST /v1/ingestao` com header `X-Api-Key: <INGEST_TOKEN>`

## Carga dos CSVs deste PC

```bash
# no .env da raiz:
# DATABASE_URL=postgresql://c4istar:c4istar@127.0.0.1:5432/c4istar
# CLIENTE_DOCUMENTO=02401001581

.\venv\Scripts\python.exe -m db.migrar_csv --documento 02401001581
```

## ECS (resumo)

1. Suba RDS Postgres (ou use o serviço `db` só em Lightsail).
2. Build da imagem `nuvem/Dockerfile.api` e push ao ECR.
3. Task Fargate com `DATABASE_URL` e `INGEST_TOKEN`.
4. ALB na porta 8080.
