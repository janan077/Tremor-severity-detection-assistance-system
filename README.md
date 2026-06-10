# Tremor Review Project

This project now uses:

- `backend/main.py` for the FastAPI API
- `web_server.py` for the Flask web app
- `templates/` for the current user interface
- `models/mobilenet_tremor_detector_latest.pth` for the latest active model

## Current Run Method

Open two terminals in the project folder and run:

```powershell
.\.venv_run\Scripts\python.exe backend\main.py
```

```powershell
.\.venv_run\Scripts\python.exe web_server.py
```

Then open:

- `http://localhost:5000`
- `http://localhost:8000/health`

## Important Notes

- The current UI is the Flask app, not the old React app.
- The `frontend/` folder is legacy project material and is not the active interface.
- The current active model uses 7 tremor classes.
- Severity is still derived from tremor-type mapping, not from a separately trained severity model.

## Main Folders

- `backend/` - FastAPI backend
- `templates/` - active Flask UI templates
- `models/` - active model files
- `instance/` - SQLite DB and Flask secret key
- `uploads/` - uploaded files
- `datasets/` - original dataset
- `datasets_reclassified/` - corrected dataset copy
- `frames_reclassified/` - retraining frames

## Deployment

Deployment-ready files are included:

- `Dockerfile.backend`
- `Dockerfile.web`
- `docker-compose.yml`
- `render.yaml`
- `DEPLOYMENT.md`
