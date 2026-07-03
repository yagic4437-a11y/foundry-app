from app.models import AssessmentOutput
from app.storage import AssessmentRepository


def minimal_assessment(use_case_id: str = "uc-1") -> AssessmentOutput:
    return AssessmentOutput.model_validate(
        {
            "use_case_id": use_case_id,
            "feasibility": {
                "data_availability": {"score": 3, "note": "Enough starting data."},
                "solution_approach": {"type": "assemble", "note": "Compose existing services."},
                "integration": {
                    "systems_to_integrate": ["CRM"],
                    "integration_type": "augment",
                    "user_interface": "Internal dashboard",
                    "process_owner": "Technical department",
                    "note": "No replacement required.",
                },
                "effort_estimate": {"range": "4-8 weeks", "note": "Pilot scope."},
                "technical_risk": {"score": 2, "note": "Manageable."},
                "overall_score": 3.4,
            },
            "compliance": {
                "gdpr": {"personal_data_involved": True, "note": "Employee data may appear."},
                "eu_ai_act": {
                    "suggested_risk_class": "limited",
                    "reasoning": "May interact with users.",
                    "cited_articles": ["GDPR Article 6"],
                    "confidence": "medium",
                    "needs_human_review": True,
                },
                "verdict": "conditional",
            },
            "cost": {
                "one_time_estimate_eur": "EUR 10,000-25,000",
                "ongoing_monthly_eur": "EUR 500-1,500",
                "sources": [{"title": "Vendor pricing", "url": "https://example.com"}],
            },
            "recommendation_summary": "Run a human-reviewed pilot.",
        }
    )


def test_repository_saves_and_fetches_assessment(tmp_path):
    repo = AssessmentRepository(tmp_path / "assessments.sqlite")
    assessment = minimal_assessment()

    repo.save(assessment, status="in_review")
    stored = repo.get("uc-1")

    assert stored is not None
    assert stored.assessment.use_case_id == "uc-1"
    assert stored.status == "in_review"


def test_repository_confirm_marks_human_reviewed_and_stores_overrides(tmp_path):
    repo = AssessmentRepository(tmp_path / "assessments.sqlite")
    repo.save(minimal_assessment(), status="in_review")

    confirmed = repo.confirm("uc-1", {"technical_risk": "accepted by reviewer"})

    assert confirmed.assessment.human_reviewed is True
    assert confirmed.assessment.reviewer_overrides == {"technical_risk": "accepted by reviewer"}
    assert confirmed.status == "sent"
