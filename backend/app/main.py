from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.assessment import AssessmentService
from app.chatbot_adapter import normalize_chatbot_session
from app.config import get_settings
from app.legal_sources import load_legal_chunks
from app.llm_client import SiliconFlowClient
from app.models import ChatbotSessionInput, ConfirmRequest, StoredAssessment, UseCaseInput
from app.storage import AssessmentRepository


def create_app(database_path: str | Path | None = None, use_live_services: bool = True) -> FastAPI:
    settings = get_settings()
    repository = AssessmentRepository(database_path or settings.database_path)
    llm_client = None
    if use_live_services and settings.siliconflow_api_key:
        llm_client = SiliconFlowClient(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.siliconflow_model,
            embedding_model=settings.siliconflow_embedding_model,
            embedding_fallback_models=settings.embedding_fallback_models,
        )
    service = AssessmentService(
        llm_client=llm_client,
        legal_chunks=load_legal_chunks(settings.legal_docs_path),
        use_live_services=use_live_services and llm_client is not None,
    )

    app = FastAPI(title="AI Use-Case Technical & Compliance Assessment API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/assess")
    async def list_assessments() -> list[StoredAssessment]:
        return repository.list_all()

    @app.post("/assess")
    async def assess(use_case: UseCaseInput):
        assessment = await service.assess(use_case)
        repository.save(assessment, status="in_review", source_use_case=use_case)
        return assessment

    @app.post("/assess/session")
    async def assess_chatbot_session(session: ChatbotSessionInput):
        use_case = normalize_chatbot_session(session)
        assessment = await service.assess(use_case)
        repository.save(assessment, status="in_review", source_use_case=use_case)
        return assessment

    @app.get("/assess/{use_case_id}")
    async def get_assessment(use_case_id: str) -> StoredAssessment:
        stored = repository.get(use_case_id)
        if stored is None:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return stored

    @app.post("/assess/{use_case_id}/confirm")
    async def confirm_assessment(use_case_id: str, request: ConfirmRequest) -> StoredAssessment:
        try:
            return repository.confirm(use_case_id, request.reviewer_overrides)
        except KeyError:
            raise HTTPException(status_code=404, detail="Assessment not found") from None

    return app


app = create_app()
