# Atlas API

Internal service powering Acme customer dashboards.

## Stack
- FastAPI
- MySQL (db-primary-01)
- Redis (redis-cache-01)

## Local
```bash
cp .env.example .env
docker compose up --build
```

Owner: Bob Smith <bob.smith@acme-tech.internal>
