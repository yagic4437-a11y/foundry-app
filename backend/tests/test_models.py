from app.models import AssessmentOutput, UseCaseInput


def sample_use_case_payload():
    return {
        "id": "uc-1",
        "title": "Digitize paper box measurements",
        "problem_description": "Operators write box measurements on paper.",
        "department": "Operations",
        "current_process": "Manual measuring and paper forms.",
        "data_mentioned": "Box dimensions, operator notes",
        "expected_benefit": "Reduce retyping and errors.",
        "company_profile": {
            "industry": "Manufacturing",
            "size": "Medium",
            "region": "EU",
            "existing_tech_stack": ["Excel", "ERP"],
        },
    }


def test_use_case_input_accepts_project_contract():
    use_case = UseCaseInput.model_validate(sample_use_case_payload())

    assert use_case.id == "uc-1"
    assert use_case.company_profile.existing_tech_stack == ["Excel", "ERP"]


def test_assessment_output_uses_required_aliases_and_defaults():
    assessment = AssessmentOutput.model_validate(
        {
            "use_case_id": "uc-1",
            "feasibility": {
                "data_availability": {"score": 3, "note": "Data exists on paper."},
                "solution_approach": {"type": "assemble", "note": "Use OCR plus workflow UI."},
                "integration": {
                    "systems_to_integrate": ["ERP"],
                    "integration_type": "augment",
                    "user_interface": "Reviewer dashboard",
                    "process_owner": "Operations",
                    "note": "Keep current ERP as system of record.",
                },
                "effort_estimate": {"range": "4-8 weeks", "note": "Small pilot."},
                "technical_risk": {"score": 2, "note": "OCR quality risk."},
                "overall_score": 3.2,
            },
            "compliance": {
                "gdpr": {"personal_data_involved": False, "note": "No personal data mentioned."},
                "eu_ai_act": {
                    "suggested_risk_class": "minimal",
                    "reasoning": "Measurement extraction is low impact.",
                    "cited_articles": ["AI Act Article 3"],
                    "confidence": "medium",
                    "needs_human_review": True,
                },
                "verdict": "conditional",
            },
            "cost": {
                "one_time_estimate_eur": "EUR 5,000-15,000",
                "ongoing_monthly_eur": "EUR 100-500",
                "sources": [{"title": "Example pricing", "url": "https://example.com/pricing"}],
            },
            "recommendation_summary": "Proceed with a controlled pilot.",
            "decision_package": {
                "feasibility_questions": [
                    {
                        "question": "Is the paper measurement data consistent enough to digitize?",
                        "current_answer": "Likely yes for a pilot.",
                        "evidence": "The current process already records box dimensions on paper.",
                        "references": [
                            {
                                "title": "Use-case current process",
                                "source_type": "use_case",
                                "detail": "Manual measuring and paper forms.",
                            }
                        ],
                        "confidence": "medium",
                        "action_required": "Confirm required measurement fields and quality rules with Operations.",
                    }
                ],
                "cost_finance_questions": [],
                "compliance_questions": [],
                "reviewer_note": "Decision maker should validate assumptions before approving budget.",
            },
        }
    )

    assert assessment.human_reviewed is False
    assert assessment.reviewer_overrides == {}
    assert assessment.feasibility.solution_approach.type == "assemble"
    assert assessment.decision_package.feasibility_questions[0].references[0].source_type == "use_case"


def test_invalid_solution_type_is_rejected():
    payload = sample_use_case_payload()
    use_case = UseCaseInput.model_validate(payload)
    assert use_case.id == "uc-1"
