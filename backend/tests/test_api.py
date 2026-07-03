from fastapi.testclient import TestClient

from app.assessment import SYSTEM_PROMPT
from app.main import create_app


def sample_use_case():
    return {
        "id": "uc-api-1",
        "title": "AI support chatbot",
        "problem_description": "Customers wait too long for answers to common questions.",
        "department": "Technical department",
        "current_process": "Support agents answer repeated tickets manually.",
        "data_mentioned": "Customer questions, account identifiers, support history",
        "expected_benefit": "Reduce response times and free support staff.",
        "company_profile": {
            "industry": "Software",
            "size": "Medium",
            "region": "EU",
            "existing_tech_stack": ["Zendesk", "Slack"],
        },
    }


def sample_chatbot_session():
    return {
        "session_id": "b2f9cc3b-7308-4a3b-abca-1f35a6c69e58",
        "status": "ended",
        "category": "Problem",
        "department": "Operations",
        "answers": [
            {"question_id": "title", "answer": "Digitize paper box measurements", "is_followup": False},
            {
                "question_id": "description_problem",
                "answer": "Operators measure boxes and write the dimensions on paper.",
                "is_followup": False,
            },
            {
                "question_id": "description_problem",
                "answer": "The paper forms are later retyped into ERP.",
                "is_followup": True,
            },
            {"question_id": "goal", "answer": "Remove paperwork and reduce typing errors.", "is_followup": False},
            {"question_id": "department", "answer": "Operations", "is_followup": False},
            {"question_id": "tools_systems", "answer": "ERP, Excel", "is_followup": False},
            {"question_id": "data_involved", "answer": "Box dimensions, timestamps, shift IDs", "is_followup": False},
        ],
        "transcript": [],
    }


def test_assess_get_and_confirm_roundtrip(tmp_path):
    app = create_app(database_path=tmp_path / "api.sqlite", use_live_services=False)
    client = TestClient(app)

    assess_response = client.post("/assess", json=sample_use_case())

    assert assess_response.status_code == 200
    payload = assess_response.json()
    assert payload["use_case_id"] == "uc-api-1"
    assert payload["human_reviewed"] is False
    assert payload["compliance"]["eu_ai_act"]["cited_articles"]

    get_response = client.get("/assess/uc-api-1")
    assert get_response.status_code == 200
    assert get_response.json()["assessment"]["use_case_id"] == "uc-api-1"

    confirm_response = client.post(
        "/assess/uc-api-1/confirm",
        json={"reviewer_overrides": {"risk_class": "limited approved"}},
    )
    assert confirm_response.status_code == 200
    confirmed = confirm_response.json()
    assert confirmed["assessment"]["human_reviewed"] is True
    assert confirmed["status"] == "sent"


def test_assess_chatbot_session_normalizes_and_assesses(tmp_path):
    app = create_app(database_path=tmp_path / "api.sqlite", use_live_services=False)
    client = TestClient(app)

    response = client.post("/assess/session", json=sample_chatbot_session())

    assert response.status_code == 200
    payload = response.json()
    assert payload["use_case_id"] == "session-b2f9cc3b-7308-4a3b-abca-1f35a6c69e58"
    assert payload["feasibility"]["integration"]["systems_to_integrate"] == ["ERP", "Excel"]
    assert payload["decision_package"]["feasibility_questions"]
    solution = payload["decision_package"]["solution_recommendation"]
    assert solution["recommended_solution"]
    assert solution["implementation_steps"]
    assert solution["references"]
    assert any(reference["source_type"] == "web" for reference in solution["references"])
    assert "market_solutions" in payload["decision_package"]
    assert all(
        item["name"] not in {"Microsoft Power Apps", "Google AppSheet", "Tulip Frontline Operations Platform"}
        for item in payload["decision_package"]["market_solutions"]
    )

    stored = client.get("/assess/session-b2f9cc3b-7308-4a3b-abca-1f35a6c69e58").json()
    assert stored["source_use_case"]["title"] == "Digitize paper box measurements"
    assert stored["source_use_case"]["company_profile"]["existing_tech_stack"] == ["ERP", "Excel"]


def test_assessment_includes_decision_maker_questions_with_references(tmp_path):
    app = create_app(database_path=tmp_path / "api.sqlite", use_live_services=False)
    client = TestClient(app)
    payload = sample_use_case()
    payload.update(
        {
            "id": "paper-box-1",
            "title": "Digitize paper box measurements",
            "problem_description": "Operators measure boxes and write dimensions on paper.",
            "current_process": "Manual measurements are written on paper and retyped into ERP.",
            "data_mentioned": "Box dimensions, timestamps, shift identifiers",
        }
    )

    response = client.post("/assess", json=payload)

    assert response.status_code == 200
    decision_package = response.json()["decision_package"]
    assert decision_package["feasibility_questions"]
    assert decision_package["cost_finance_questions"]
    assert decision_package["compliance_questions"]
    all_questions = (
        decision_package["feasibility_questions"]
        + decision_package["cost_finance_questions"]
        + decision_package["compliance_questions"]
    )
    assert all(question["references"] for question in all_questions)
    assert any(
        reference["source_type"] == "legal_rag"
        for question in decision_package["compliance_questions"]
        for reference in question["references"]
    )


def test_system_prompt_uses_decision_reviewer_instructions():
    assert "technical feasibility and compliance reviewer" in SYSTEM_PROMPT
    assert "Do not assume this is a chatbot" in SYSTEM_PROMPT
    assert "Use web search for current pricing" in SYSTEM_PROMPT


def test_get_missing_assessment_returns_404(tmp_path):
    app = create_app(database_path=tmp_path / "api.sqlite", use_live_services=False)
    client = TestClient(app)

    response = client.get("/assess/missing")

    assert response.status_code == 404
