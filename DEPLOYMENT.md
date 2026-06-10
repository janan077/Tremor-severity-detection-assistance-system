# Deployment Guide

## Architecture

This project is deployed as two services:

1. `tremor-api`
   - FastAPI backend
   - serves `/health`, `/classes`, `/classify/video`, `/classify/image`

2. `tremor-web`
   - Flask web application
   - serves login, dashboard, analysis, history, and report pages
   - calls the API using `TREMOR_API_URL`

## Environment Variables

### Web service

- `TREMOR_APP_SECRET_KEY`
- `TREMOR_API_URL`
- `WEB_HOST`
- `WEB_PORT`
- `FLASK_DEBUG`
- `OPEN_BROWSER`

### API service

- `API_HOST`
- `API_PORT`

## Docker Compose

Run locally with Docker:

```bash
docker compose up --build
```

Then open:

- `http://localhost:5000`
- `http://localhost:8000/health`

## Render / Similar Platforms

Deploy two separate web services:

1. API service
   - Dockerfile: `Dockerfile.backend`
   - Start command: built into the Dockerfile

2. Web service
   - Dockerfile: `Dockerfile.web`
   - Set `TREMOR_API_URL` to your deployed backend URL
   - Set `TREMOR_APP_SECRET_KEY` to a strong random value

## Production Notes

- Keep the `models/` folder available in production.
- Set a strong `TREMOR_APP_SECRET_KEY`.
- Do not enable `FLASK_DEBUG=true` in production.
- Persist `instance/` if you want SQLite users and reports to survive redeploys.
- Persist `uploads/` if uploaded files must remain available.
