# Group-26

*Everyone cares for the patient. We watch over the caregiver.*

A caregiver support app: care dashboard (meds/appointments/to-dos), quiet background
stress sensing (webcam rPPG, falling back to a manual check-in), an AI burnout
threshold detector combining task load with physiological stress, a proactive
paced-breathing intervention, and a closing reflection.

FastAPI backend + React (Vite) frontend.

## Backend

```
cd backend
python -m venv venv
./venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API runs at http://127.0.0.1:8000, docs at http://127.0.0.1:8000/docs. Uses SQLite (`backend/app.db`, auto-created).

Optional LLM (for the burnout reasoning and closing reflection wording only — never
for the intervene / don't-intervene decision). `backend/app/llm.py` tries providers in
order and falls back to templates if none are configured or reachable — the app never
depends on an LLM being up. Copy `backend/.env.example` to `backend/.env` and fill in
one provider:

- **Microsoft Foundry (primary):** set `AZURE_AI_ENDPOINT`, `AZURE_AI_API_KEY`, and
  `AZURE_AI_MODEL` (default `claude-sonnet-4-5`). Uses Foundry's OpenAI-compatible
  chat-completions surface.
- **Anthropic direct (fallback):** set `ANTHROPIC_API_KEY`. Used only if the Foundry
  vars are absent, so the app still runs without an Azure resource.

Everything works with all of these unset — the app falls back to built-in templated
text and never depends on the LLM being reachable.

Every LLM-backed response reports which provider actually answered — `GET
/threshold/check` returns `reasoning_source` (`"foundry"` / `"anthropic"` / `"rule"`) and
reflections carry `generated_by` (`"foundry"` / `"anthropic"` / `"template"`) — so you can
show at the demo that Foundry is genuinely in the loop, not just configured.

## Frontend

```
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173. Set `VITE_API_URL` in `frontend/.env` if the backend isn't at the default `http://127.0.0.1:8000` (see `frontend/.env.example`).

The stress monitor asks for camera access on load and estimates heart rate from the
webcam (rPPG). If the camera is denied/unavailable, or the signal stays too noisy to
trust, it automatically falls back to a manual 1-10 stress check-in — the intervention
flow works either way.

## How the pieces fit together

1. **Care Dashboard** (`frontend/src/components/Dashboard.jsx`) — meds, appointments, to-dos.
2. **Stress sensing** (`frontend/src/hooks/useStressMonitor.js`, `frontend/src/rppg.js`) —
   samples the webcam every 100ms, estimates heart rate via green-channel peak detection,
   posts a reading to `POST /stress` every 5s.
3. **AI brain** (`backend/app/scoring.py`) — `GET /threshold/check` combines the latest
   physiological score with a behavioral score from open/overdue tasks. Rule-based by
   default (reliable offline); an LLM only phrases the reasoning text if configured.
4. **Intervention** (`frontend/src/components/Intervention.jsx`) — paced breathing
   overlay; pace re-fetched from `GET /intervention/{id}/pace` every 5s so it adjusts to
   real-time stress.
5. **Reflection** (`backend/app/reflection.py`, `frontend/src/components/Reflection.jsx`) —
   closing message generated after the session ends via `POST /reflection/{id}`.

There's a 90s cooldown after a session ends before the next auto-check-in, so returning
to the dashboard doesn't immediately re-trigger another intervention.
