# AI Use-Case Assessment Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a demo-ready technical and compliance assessment module that receives structured chatbot use-case JSON, runs feasibility/compliance/cost assessment, stores the result, and lets a reviewer edit and confirm it.

**Architecture:** FastAPI owns the assessment API, Pydantic contracts, SQLite persistence, SiliconFlow LLM calls, legal document ingestion, vector retrieval, and compliance grounding. React + Tailwind owns the review queue, editable assessment view, and confirm/send screen. External services are wrapped behind small adapters so the demo still works with deterministic fallbacks if a free-tier model or network call fails.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite, pytest, httpx, OpenAI-compatible SiliconFlow API, ChromaDB, React, Vite, TypeScript, Tailwind CSS.

---

### Task 1: Backend Contract And Storage

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/storage.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/test_models.py`
- Create: `backend/tests/test_storage.py`

- [ ] Write Pydantic tests for the required input and output schemas.
- [ ] Implement schemas exactly matching the project prompt.
- [ ] Write storage tests for save/fetch/confirm behavior.
- [ ] Implement SQLite repository with JSON payload storage.
- [ ] Run `pytest backend/tests/test_models.py backend/tests/test_storage.py -q`.

### Task 2: SiliconFlow Client

**Files:**
- Create: `backend/app/llm_client.py`
- Create: `backend/tests/test_llm_client.py`

- [ ] Write tests using a fake HTTP transport for chat and embedding requests.
- [ ] Implement OpenAI-compatible `/chat/completions` and `/embeddings` calls.
- [ ] Support configurable `SILICONFLOW_MODEL`, `SILICONFLOW_EMBEDDING_MODEL`, and fallback embedding models.
- [ ] Run `pytest backend/tests/test_llm_client.py -q`.

### Task 3: Legal Corpus And RAG

**Files:**
- Create: `backend/app/legal_sources.py`
- Create: `backend/app/rag.py`
- Create: `backend/scripts/ingest_legal_docs.py`
- Create: `backend/tests/test_rag.py`

- [ ] Write article chunking and retrieval tests against short fixture documents.
- [ ] Implement official-source downloader for EUR-Lex EU AI Act and GDPR pages/PDFs, with local fallback excerpts for demo reliability.
- [ ] Implement article chunker that preserves `source`, `article`, `title`, and `text`.
- [ ] Implement ChromaDB vector store ingestion and retrieval.
- [ ] Run `pytest backend/tests/test_rag.py -q`.

### Task 4: Assessment Pipeline And API

**Files:**
- Create: `backend/app/assessment.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api.py`

- [ ] Write API tests for `POST /assess`, `GET /assess/{id}`, and `POST /assess/{id}/confirm`.
- [ ] Implement deterministic fallback assessment when LLM or search is unavailable.
- [ ] Implement three-step LLM pipeline with JSON validation and one retry.
- [ ] Implement optional web cost search adapter with source URLs.
- [ ] Run `pytest backend/tests/test_api.py -q`.

### Task 5: Frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/index.css`

- [ ] Scaffold Vite React TypeScript app.
- [ ] Build review queue, assessment editor, and confirm/send flow.
- [ ] Connect to backend API with mock fallback when backend is unavailable.
- [ ] Run `npm run build` in `frontend`.

### Task 6: End-To-End Verification

**Files:**
- Create: `README.md`
- Create: `.env.example`

- [ ] Save local `.env` with SiliconFlow key and defaults.
- [ ] Install backend and frontend dependencies.
- [ ] Run backend test suite.
- [ ] Build frontend.
- [ ] Start backend and frontend dev servers, then provide URLs.
