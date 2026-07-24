# Group-26

Full-stack app: FastAPI backend + React (Vite) frontend.

## Backend

```
cd backend
python -m venv venv
./venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at http://127.0.0.1:8000, docs at http://127.0.0.1:8000/docs. Uses SQLite (`backend/app.db`, auto-created).

## Frontend

```
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173. Set `VITE_API_URL` in `frontend/.env` if the backend isn't at the default `http://127.0.0.1:8000` (see `frontend/.env.example`).
