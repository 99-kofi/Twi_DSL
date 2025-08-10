# Twi DSL Playground (Backend + Frontend)

## Layout
- `backend/` — FastAPI service that translates & executes Twi DSL
- `frontend/` — Streamlit UI with custom Twi DSL syntax highlighting

## Deploy Backend (Render)
- Point Render to `backend/` folder (or use separate repo)
- Build command: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

## Deploy Frontend (Streamlit Cloud or Render)
- For Streamlit Cloud: point to `frontend/app.py`
- For Render: use `Procfile` above and `requirements.txt`.

## Security
This is a prototype. Do **not** execute untrusted code in a shared production environment. Replace in-process execution with an isolated runner for production.


