# AI Use-Case Technical & Compliance Assessment Hub

This project receives a structured chatbot use-case JSON object, assesses technical feasibility, integration, cost, GDPR, and EU AI Act considerations, then lets a reviewer edit and confirm the final package.

## Backend

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/ingest_legal_docs.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The backend reads `SILICONFLOW_API_KEY` from `.env`. The configured chat model is `Qwen/Qwen3-8B`; the embedding model is `Qwen/Qwen3-Embedding-8B` with BGE fallbacks.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

## API

- `POST /assess`: accepts the creator/community use-case JSON and returns an editable assessment package.
- `GET /assess`: lists stored assessments.
- `GET /assess/{id}`: fetches one stored assessment.
- `POST /assess/{id}/confirm`: marks a reviewed assessment as sent.

## Chatbot Integration

Use `session_id` or `use_case_id` as the primary identifier. `username` should only be display/filter metadata because one user can submit multiple ideas.
