# SQL Query Formatter
A fast, developer‑friendly SQL query formatter built with FastAPI and vanilla JavaScript.

## Features
- Instant SQL formatting in the browser
- Clean indentation and readable formatting
- Uppercase SQL keywords
- Dark mode developer UI
- Copy formatted SQL to clipboard
- Floating feedback widget backed by Google Sheets
- Keyboard shortcut (Cmd/Ctrl + Enter)
- Rate‑limited API endpoint

## Tech Stack
- Python
- FastAPI
- sqlparse
- slowapi (rate limiting)
- Vanilla JS frontend served as static files

## Project Layout
- backend/
- frontend/
- requirements.txt
- Dockerfile

## Live Demo
Once deployed, the tool will be available at:

```
https://<your-domain>
```

Until a custom domain is configured, you can access the temporary deployment URL provided by the hosting platform.

## Environment Variables
The app supports environment-based configuration via `.env` or host environment values.

- `ALLOWED_ORIGINS`
  - Comma-separated CORS origins.
  - Default: `http://localhost:8000,http://127.0.0.1:8000,http://127.0.0.1:5500`
- `LOG_LEVEL`
  - Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Default: `INFO`
- `FEEDBACK_WEBHOOK_URL`
  - Google Apps Script Web App `/exec` URL used to store feedback rows in Google Sheets.
- `FEEDBACK_WEBHOOK_TOKEN`
  - Shared secret appended by the backend as the `token` query param when posting to Apps Script.
- `APP_ENV`
  - Metadata label stored with feedback submissions.
  - Default: `local`

Example `.env`:

```env
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
LOG_LEVEL=INFO
FEEDBACK_WEBHOOK_URL=https://script.google.com/macros/s/<deployment-id>/exec
FEEDBACK_WEBHOOK_TOKEN=replace-with-your-shared-secret
APP_ENV=local
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

## Feedback Setup (Google Sheets)
1. Create a Google Sheet tab with headers:
  - `submitted_at`, `source`, `email`, `message`, `meta_ip`, `meta_user_agent`, `meta_env`, `request_id`
2. In that sheet, open Extensions -> Apps Script and add a `doPost(e)` handler.
3. Set Apps Script properties:
  - `FEEDBACK_TOKEN`
  - `SHEET_NAME`
4. Deploy the script as a Web App:
  - Execute as: `Me`
  - Who has access: `Anyone`
5. Copy the Web App `/exec` URL into `FEEDBACK_WEBHOOK_URL`.
6. Set the same shared secret in both Apps Script (`FEEDBACK_TOKEN`) and backend (`FEEDBACK_WEBHOOK_TOKEN`).

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
  -e FEEDBACK_WEBHOOK_URL=https://script.google.com/macros/s/<deployment-id>/exec \
  -e FEEDBACK_WEBHOOK_TOKEN=replace-with-your-shared-secret \
  -e APP_ENV=container \
  sql-query-formatter
```

## Deploy to Railway
1. Push this repository to GitHub.
2. Create a new Railway project from the repo.
3. Railway auto-detects Dockerfile and builds image.
4. Set environment variables in Railway:
   - `ALLOWED_ORIGINS` (your production domain)
   - `LOG_LEVEL=INFO`
  - `FEEDBACK_WEBHOOK_URL`
  - `FEEDBACK_WEBHOOK_TOKEN`
  - `APP_ENV=production`
5. Deploy and verify the service:
   - `/healthz` returns `{"status":"ok"}`
   - `/` loads the SQL formatter UI
   - `/format` formats SQL queries
  - Feedback submissions create rows in Google Sheets

## Deploy to Render
1. Create a new Web Service from your GitHub repo.
2. Choose Docker deployment (Render detects Dockerfile).
3. Set environment variables:
   - `ALLOWED_ORIGINS` (your production domain)
   - `LOG_LEVEL=INFO`
  - `FEEDBACK_WEBHOOK_URL`
  - `FEEDBACK_WEBHOOK_TOKEN`
  - `APP_ENV=production`
4. Deploy and test:
   - `/healthz`
   - `/`
   - `POST /format`
  - `POST /feedback`

## Use Cases
This tool is useful for:

- Developers quickly formatting SQL queries
- Cleaning up messy SQL before code reviews
- Improving readability of complex queries
- Preparing SQL for documentation or sharing

## API Endpoints
- `POST /format`
  - Request body: `{ "sql": "SELECT * FROM users" }`
  - Validates non-empty SQL and max size.
  - Rate-limited: 60 requests/minute/IP.
- `POST /feedback`
  - Request body: `{ "email": "optional@example.com", "message": "Feedback text" }`
  - Validates message length and optional email format.
  - Rate-limited: 10 requests/minute/IP.
  - Forwards submissions to Google Apps Script for storage in Google Sheets.
- `GET /healthz`
  - Returns `{ "status": "ok" }`
