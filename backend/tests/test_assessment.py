import asyncio

import pytest

from app.assessment import AssessmentService
from app.assessment import _market_solution_items
from app.models import UseCaseInput


class SlowClient:
    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict:
        await asyncio.sleep(2)
        return {}


def sample_use_case() -> UseCaseInput:
    return UseCaseInput.model_validate(
        {
            "id": "timeout-1",
            "title": "Digitize paper box measurements",
            "problem_description": "Operators record dimensions on paper.",
            "department": "Operations",
            "current_process": "Paper forms are later retyped into ERP.",
            "data_mentioned": "Box dimensions and timestamps",
            "expected_benefit": "Reduce typing errors.",
            "company_profile": {
                "industry": "Manufacturing",
                "size": "Medium",
                "region": "EU",
                "existing_tech_stack": ["ERP"],
            },
        }
    )


@pytest.mark.asyncio
async def test_live_assessment_times_out_to_fallback_quickly():
    service = AssessmentService(
        llm_client=SlowClient(),
        legal_chunks=[],
        use_live_services=True,
        live_timeout_seconds=0.05,
    )

    assessment = await service.assess(sample_use_case())

    assert assessment.use_case_id == "timeout-1"
    assert assessment.decision_package.feasibility_questions


@pytest.mark.asyncio
async def test_low_information_input_is_not_over_assessed():
    service = AssessmentService(llm_client=None, legal_chunks=[], use_live_services=False)
    use_case = UseCaseInput.model_validate(
        {
            "id": "low-info-1",
            "title": "adadasd",
            "problem_description": "dddas dwadawd",
            "department": "asdasd",
            "current_process": "dddas dwadawd",
            "data_mentioned": "No data was specified.",
            "expected_benefit": "sdadasd asdasd",
            "company_profile": {
                "industry": "Not specified",
                "size": "Not specified",
                "region": "EU",
                "existing_tech_stack": [],
            },
        }
    )

    assessment = await service.assess(use_case)

    assert assessment.feasibility.overall_score == 1
    assert "Insufficient information" in assessment.recommendation_summary
    assert assessment.cost.one_time_estimate_eur == "Not estimated"
    assert assessment.compliance.eu_ai_act.confidence == "low"
    assert assessment.compliance.eu_ai_act.cited_articles == []
    assert assessment.decision_package.solution_recommendation.recommended_solution.startswith(
        "No implementation solution should be approved"
    )
    assert all(
        reference.source_type != "legal_rag"
        for question in assessment.decision_package.compliance_questions
        for reference in question.references
    )


def test_market_solution_items_do_not_use_static_vendor_fallbacks():
    items = _market_solution_items(sample_use_case(), [])

    assert len(items) == 1
    assert items[0]["name"] == "No market candidates found"
    assert items[0]["references"][0]["source_type"] == "estimation"
