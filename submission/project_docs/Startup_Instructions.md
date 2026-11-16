# Startup Instructions

These commands assume the complete project checkout and its local dependencies are available. The submission package intentionally excludes virtual environments, `node_modules`, proprietary raw data, local availability overlay, and secrets.

## FastAPI backend

From the project root, in PowerShell:

```powershell
api\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

The local API is available at `http://127.0.0.1:8000`; the health endpoint is `/api/v1/health`.

## React frontend

In a second terminal:

```powershell
cd frontend
npm.cmd run dev
```

Vite serves the frontend at `http://127.0.0.1:5173`. The frontend defaults to the local API at `http://127.0.0.1:8000/api/v1`.

If setting up a fresh development checkout, install dependencies from `api/requirements.txt` and `frontend/package.json` using the project's documented setup process. Do not add `.env` files to the submission.

## Existing Streamlit dashboard

From the project root, if the project environment is installed:

```powershell
.\venv\Scripts\streamlit.exe run dashboard/app.py
```

This dashboard runs separately from the React frontend and FastAPI adapter.
