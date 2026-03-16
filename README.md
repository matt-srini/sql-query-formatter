# SQL Query Formatter API

Lightweight FastAPI-based SQL formatter for developers.

## Stack
- Python
- FastAPI
- sqlparse
- slowapi (rate limiting)
- Vanilla JS frontend served as static files

## Project Structure
- backend/
- frontend/
- requirements.txt
- Dockerfile

## Environment Variables
The app supports environment-based configuration via `.env` or host environment values.

- `ALLOWED_ORIGINS`
  - Comma-separated CORS origins.
  - Default: `http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5500`
- `LOG_LEVEL`
  - Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Default: `INFO`

Example `.env`:

```env
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
LOG_LEVEL=INFO
```

## Run Locally
1. Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run server:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

4. Open app:
- `http://127.0.0.1:8000/`
- Health check: `http://127.0.0.1:8000/healthz`

## Build Docker Image
From project root:

```bash
docker build -t sql-query-formatter .
```

## Run Docker Container

```bash
docker run --rm -p 8000:8000 \
  -e ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000 \
  -e LOG_LEVEL=INFO \
  sql-query-formatter
```

## Deploy to Railway
1. Push this repository to GitHub.
2. Create a new Railway project from the repo.
3. Railway auto-detects Dockerfile and builds image.
4. Set environment variables in Railway:
   - `ALLOWED_ORIGINS` (your production domain)
   - `LOG_LEVEL=INFO`
5. Deploy and verify:
   - `/healthz` returns `{\"status\":\"ok\"}`
   - `/` serves frontend
   - `/format` formats SQL

## Deploy to Render
1. Create a new Web Service from your GitHub repo.
2. Choose Docker deployment (Render detects Dockerfile).
3. Set environment variables:
   - `ALLOWED_ORIGINS` (your production domain)
   - `LOG_LEVEL=INFO`
4. Deploy and test:
   - `/healthz`
   - `/`
   - `POST /format`

## API Endpoints
- `POST /format`
  - Request body: `{ "sql": "SELECT * FROM users" }`
  - Validates non-empty SQL and max size.
  - Rate-limited: 60 requests/minute/IP.
- `GET /healthz`
  - Returns `{ "status": "ok" }`
