from app.models import ChatbotSessionInput, UseCaseInput


def normalize_chatbot_session(session: ChatbotSessionInput) -> UseCaseInput:
    answers = _answers_by_question(session)
    tools = _split_tools(answers.get("tools_systems", ""))
    department = answers.get("department") or session.department or "Unknown department"
    description = answers.get("description_problem", "")
    return UseCaseInput.model_validate(
        {
            "id": f"session-{session.session_id}",
            "title": answers.get("title") or session.category or f"Use case {session.session_id}",
            "problem_description": description or "No problem description was provided.",
            "department": department,
            "current_process": description or "Current process was not described.",
            "data_mentioned": answers.get("data_involved") or "",
            "expected_benefit": answers.get("goal") or "",
            "company_profile": {
                "industry": "Not specified",
                "size": "Not specified",
                "region": "EU",
                "existing_tech_stack": tools,
            },
        }
    )


def _answers_by_question(session: ChatbotSessionInput) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for answer in session.answers:
        value = answer.answer.strip()
        if not value:
            continue
        grouped.setdefault(answer.question_id, []).append(value)
    return {question_id: "\n".join(values) for question_id, values in grouped.items()}


def _split_tools(raw_tools: str) -> list[str]:
    return [item.strip() for item in raw_tools.replace(";", ",").split(",") if item.strip()]
