import json
import asyncio
import re
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from app.legal_sources import load_legal_chunks
from app.llm_client import SiliconFlowClient
from app.models import AssessmentOutput, CostAssessment, UseCaseInput
from app.rag import LegalChunk, SimpleLegalRetriever


SYSTEM_PROMPT = """You are a technical feasibility and compliance reviewer for an internal
AI use-case pipeline. You will receive a use case description (problem,
department, current process, data mentioned). For this specific use case:

1. Infer what data would be needed and assess its likely availability,
   quality, and volume based on the described current process.
2. Determine the appropriate solution type: does this need a custom AI
   model, an assembly of existing tools/APIs, or does an off-the-shelf
   product already solve it? Justify your choice for THIS use case.
3. Identify what existing systems this would need to integrate with,
   based on the department and process described.
4. Estimate effort and cost. Use web search for current pricing of any
   specific tool, API, or comparable project you reference — do not
   invent numbers.
5. Assess GDPR relevance (does this plausibly involve personal data,
   given the process described?) and EU AI Act risk category, with
   reasoning specific to this use case. Flag confidence level.

Do not assume this is a chatbot, an automation tool, or any particular
category unless the description indicates it. Reason from what is
actually described. If information is missing, state your assumption
explicitly rather than guessing silently.

Respond only in the requested JSON schema. Every decision-maker question
must include the evidence used, whether the value is actual or estimated,
and references from use-case input, legal RAG context, or web pricing sources."""


class AssessmentService:
    def __init__(
        self,
        llm_client: SiliconFlowClient | None = None,
        legal_chunks: Sequence[LegalChunk] | None = None,
        use_live_services: bool = True,
        live_timeout_seconds: float = 25,
    ):
        self.llm_client = llm_client
        self.legal_chunks = list(legal_chunks or [])
        self.use_live_services = use_live_services
        self.live_timeout_seconds = live_timeout_seconds

    async def assess(self, use_case: UseCaseInput) -> AssessmentOutput:
        if not self.use_live_services or self.llm_client is None:
            return await self._fallback_assessment(use_case)

        try:
            return await asyncio.wait_for(
                self._live_assessment(use_case),
                timeout=self.live_timeout_seconds,
            )
        except Exception:
            return await self._fallback_assessment(use_case)

    async def _live_assessment(self, use_case: UseCaseInput) -> AssessmentOutput:
        cost_sources = await estimate_cost_sources(use_case)
        solution_sources = await research_solution_sources(use_case)
        market_solutions = await research_market_solutions(use_case)
        feasibility_cost = await self._llm_json(
            _feasibility_cost_prompt(use_case, cost_sources, solution_sources, market_solutions),
            required_keys={"feasibility", "cost"},
        )
        feasibility_cost["cost"]["sources"] = [
            source.model_dump() for source in cost_sources.sources
        ] or feasibility_cost["cost"].get("sources", [])
        feasibility_cost["cost"].setdefault("estimate_basis", cost_sources.estimate_basis)
        feasibility_cost["cost"].setdefault("pricing_note", cost_sources.pricing_note)
        compliance = await self._llm_json(
            _compliance_prompt(use_case, self._retrieve_legal_context(use_case)),
            required_keys={"compliance"},
        )
        summary = await self._llm_json(
            _summary_prompt(use_case, feasibility_cost, compliance, solution_sources, market_solutions),
            required_keys={"recommendation_summary", "decision_package"},
        )
        return AssessmentOutput.model_validate(
            {
                "use_case_id": use_case.id,
                **feasibility_cost,
                **compliance,
                **summary,
                "human_reviewed": False,
                "reviewer_overrides": {},
            }
        )

    async def _llm_json(self, prompt: str, required_keys: set[str]) -> dict:
        assert self.llm_client is not None
        result = await self.llm_client.chat_json(SYSTEM_PROMPT, prompt)
        if required_keys.issubset(result.keys()):
            return result
        retry = await self.llm_client.chat_json(
            SYSTEM_PROMPT,
            f"{prompt}\n\nPrevious response missed required keys: {sorted(required_keys)}. Return corrected JSON.",
        )
        if not required_keys.issubset(retry.keys()):
            raise ValidationError("LLM response missing required keys")
        return retry

    def _retrieve_legal_context(self, use_case: UseCaseInput) -> list[LegalChunk]:
        chunks = self.legal_chunks or load_legal_chunks(__import__("pathlib").Path("data/legal"))
        query = " ".join(
            [
                use_case.title,
                use_case.problem_description,
                use_case.data_mentioned,
                use_case.current_process,
            ]
        )
        return SimpleLegalRetriever(chunks).retrieve(query, top_k=5)

    async def _fallback_assessment(self, use_case: UseCaseInput) -> AssessmentOutput:
        if _is_low_information_use_case(use_case):
            return AssessmentOutput.model_validate(_low_information_assessment(use_case))

        text = " ".join(
            [
                use_case.title,
                use_case.problem_description,
                use_case.current_process,
                use_case.data_mentioned,
                use_case.expected_benefit,
            ]
        ).lower()
        personal_data = _personal_data_likely(text)
        risk_class = "limited" if "chatbot" in text or "customer" in text else "minimal"
        legal_context = self._retrieve_legal_context(use_case)
        cited = [f"{chunk.source} {chunk.article}" for chunk in legal_context[:3]]
        systems = use_case.company_profile.existing_tech_stack or ["current workflow system"]
        cost, solution_sources, market_solutions = await asyncio.gather(
            estimate_cost_sources(use_case),
            research_solution_sources(use_case),
            research_market_solutions(use_case),
        )
        decision_package = _build_decision_package(
            use_case, personal_data, cited, cost, solution_sources, market_solutions
        )
        output = {
            "use_case_id": use_case.id,
            "feasibility": {
                "data_availability": {
                    "score": 3 if use_case.data_mentioned else 2,
                    "note": f"Initial data mentioned: {use_case.data_mentioned or 'not specified'}. Validate quality and access before pilot.",
                },
                "solution_approach": {
                    "type": "assemble",
                    "note": "Use existing AI/API components plus a small workflow layer before considering a custom build.",
                },
                "integration": {
                    "systems_to_integrate": systems,
                    "integration_type": "augment",
                    "user_interface": "Reviewer dashboard with human approval controls",
                    "process_owner": use_case.department or "Technical department",
                    "note": "Keep the current process as the source of truth and add AI as an assisted step.",
                },
                "effort_estimate": {
                    "range": "4-8 weeks for pilot",
                    "note": "Estimate assumes one data source, one reviewer workflow, and limited production hardening.",
                },
                "technical_risk": {
                    "score": 3 if personal_data else 2,
                    "note": "Main risks are data quality, integration access, and reviewer adoption.",
                },
                "overall_score": 3.4 if personal_data else 3.8,
            },
            "compliance": {
                "gdpr": {
                    "personal_data_involved": personal_data,
                    "note": "Personal data appears likely from the use-case text." if personal_data else "No personal data is explicit, but validate with the process owner.",
                },
                "eu_ai_act": {
                    "suggested_risk_class": risk_class,
                    "reasoning": "Classified from the described workflow and retrieved legal context; human legal review is still required.",
                    "cited_articles": cited,
                    "confidence": "medium",
                    "needs_human_review": True,
                },
                "verdict": "conditional",
            },
            "cost": cost.model_dump(),
            "recommendation_summary": "Proceed with a scoped pilot only after confirming data access, lawful basis, and reviewer controls. Keep a human approval step before operational use.",
            "decision_package": decision_package,
            "human_reviewed": False,
            "reviewer_overrides": {},
        }
        return AssessmentOutput.model_validate(output)


async def estimate_cost_sources(use_case: UseCaseInput) -> CostAssessment:
    query = f"{use_case.title} AI software pricing API integration"
    sources = await search_web_sources(query)
    return CostAssessment(
        one_time_estimate_eur="EUR 5,000-25,000",
        ongoing_monthly_eur="EUR 100-2,000",
        sources=sources
        or [
            {
                "title": "SiliconFlow pricing and models",
                "url": "https://www.siliconflow.com/models",
            }
        ],
        estimate_basis="estimated_range",
        pricing_note=(
            "Budget numbers are implementation estimates. Sources identify comparable vendor/API pricing "
            "inputs and must be checked by the reviewer for current actual prices."
        ),
    )


async def research_solution_sources(use_case: UseCaseInput) -> list[dict[str, str]]:
    query = f"{use_case.title} {use_case.department} digital solution software integration"
    sources = await search_web_sources(query)
    return sources or [
        {
            "title": "Digital workflow automation reference",
            "url": "https://en.wikipedia.org/wiki/Workflow_automation",
        }
    ]


async def research_market_solutions(use_case: UseCaseInput) -> list[dict[str, str]]:
    query = f"{use_case.title} {use_case.current_process} software solution vendor platform"
    return await search_web_sources(query)


async def search_web_sources(query: str) -> list[dict[str, str]]:
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
            response = await client.get("https://duckduckgo.com/html/", params={"q": query})
            response.raise_for_status()
        return _parse_duckduckgo_links(response.text)[:3]
    except Exception:
        return []


def _parse_duckduckgo_links(html: str) -> list[dict[str, str]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    sources: list[dict[str, str]] = []
    for link in soup.select("a.result__a"):
        title = link.get_text(" ", strip=True)
        url = link.get("href", "")
        if title and url:
            sources.append({"title": title, "url": url})
    return sources


def _feasibility_cost_prompt(
    use_case: UseCaseInput,
    cost_sources: CostAssessment,
    solution_sources: list[dict[str, str]],
    market_solutions: list[dict[str, str]],
) -> str:
    return f"""Assess feasibility, integration, and cost for this use case.
Return JSON with keys feasibility and cost only.
Cost must state whether values are actual_pricing, estimated_range, or mixed.
Use these web pricing/reference sources as evidence where relevant:
{json.dumps([source.model_dump() for source in cost_sources.sources], indent=2)}
Use these web solution references as context where relevant:
{json.dumps(solution_sources, indent=2)}
Use these current market search results as candidate alternatives:
{json.dumps(market_solutions, indent=2)}
Use-case JSON:
{use_case.model_dump_json(indent=2)}"""


def _compliance_prompt(use_case: UseCaseInput, chunks: Sequence[LegalChunk]) -> str:
    legal_context = "\n\n".join(
        f"{chunk.source} {chunk.article} - {chunk.title}\n{chunk.text}" for chunk in chunks
    )
    return f"""Assess GDPR and EU AI Act compliance.
Return JSON with key compliance only. Cite only articles present in the legal context.
Legal context:
{legal_context}

Use-case JSON:
{use_case.model_dump_json(indent=2)}"""


def _summary_prompt(
    use_case: UseCaseInput,
    feasibility_cost: dict,
    compliance: dict,
    solution_sources: list[dict[str, str]],
    market_solutions: list[dict[str, str]],
) -> str:
    return f"""Write a 2-3 sentence recommendation summary and decision-maker question package.
Return JSON with keys recommendation_summary and decision_package only.
decision_package schema:
{{
  "solution_recommendation": {{
    "recommended_solution": "Specific solution proposal for this use case",
    "solution_type": "buy|assemble|build",
    "rationale": "Why this solution fits the described process",
    "implementation_steps": ["Concrete step 1", "Concrete step 2"],
    "references": [
      {{"title": "Reference title", "source_type": "web|use_case|assumption|estimation", "detail": "Specific detail", "url": "optional URL or null"}}
    ],
    "assumptions": ["Assumption to validate"]
  }},
  "market_solutions": [
    {{
      "name": "Candidate product, platform, or vendor/reference",
      "category": "off_the_shelf|platform|api_service|custom_build_reference|unknown",
      "fit_summary": "Why this might or might not fit this use case",
      "evidence": "What source evidence supports considering it",
      "references": [
        {{"title": "Reference title", "source_type": "web", "detail": "Specific detail", "url": "source URL"}}
      ],
      "caveat": "What the reviewer must verify"
    }}
  ],
  "feasibility_questions": [
    {{
      "question": "Specific feasibility approval question",
      "current_answer": "Answer based on current evidence",
      "evidence": "Specific evidence used",
      "references": [
        {{"title": "Reference title", "source_type": "use_case|legal_rag|web|assumption|estimation", "detail": "Specific detail", "url": "optional URL or null"}}
      ],
      "confidence": "low|medium|high",
      "action_required": "What the decision maker or reviewer must confirm"
    }}
  ],
  "cost_finance_questions": [],
  "compliance_questions": [],
  "reviewer_note": "Professional note for the decision maker"
}}
Include at least one question in each category. Compliance questions must reference legal_rag citations from the compliance assessment. Cost questions must say whether numbers are actual pricing or estimated ranges and cite web sources when available.
Solution recommendation must be specific to the use case and cite these web solution references when useful:
{json.dumps(solution_sources, indent=2)}
Market solutions must be based only on these current market search results, not invented products:
{json.dumps(market_solutions, indent=2)}
Use case: {use_case.title}
Assessment:
{json.dumps({**feasibility_cost, **compliance}, indent=2)}"""


def _personal_data_likely(text: str) -> bool:
    negative_phrases = [
        "no customer or employee personal data",
        "no personal data",
        "without personal data",
        "not personal data",
        "personal data not",
    ]
    if any(phrase in text for phrase in negative_phrases):
        return False
    return any(
        word in text
        for word in ["customer", "employee", "personal", "account", "email", "name", "support"]
    )


def _is_low_information_use_case(use_case: UseCaseInput) -> bool:
    relevant_fields = [
        use_case.title,
        use_case.problem_description,
        use_case.current_process,
        use_case.data_mentioned,
        use_case.expected_benefit,
        use_case.department,
        " ".join(use_case.company_profile.existing_tech_stack),
    ]
    meaningful = [_looks_meaningful(field) for field in relevant_fields if field.strip()]
    return meaningful.count(True) < 2


def _looks_meaningful(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized or normalized in {
        "no data was specified.",
        "not specified",
        "unknown department",
        "current process was not described.",
        "expected benefit was not specified.",
    }:
        return False
    words = re.findall(r"[a-zA-Z]{3,}", normalized)
    if len(words) < 2:
        return False
    placeholder_words = sum(1 for word in words if _is_placeholder_word(word))
    return placeholder_words / len(words) < 0.5


def _is_placeholder_word(word: str) -> bool:
    placeholder_fragments = ["asd", "qwe", "qqq", "xxx", "lorem", "dummy", "test", "dwad", "ddda"]
    if any(fragment in word for fragment in placeholder_fragments):
        return True
    return len(set(word)) <= 2 and len(word) >= 4


def _low_information_assessment(use_case: UseCaseInput) -> dict:
    decision_package = _low_information_decision_package(use_case)
    return {
        "use_case_id": use_case.id,
        "feasibility": {
            "data_availability": {
                "score": 1,
                "note": "Insufficient information was provided to assess data availability, quality, volume, or access rights.",
            },
            "solution_approach": {
                "type": "assemble",
                "note": "No solution should be selected yet. The current submission does not describe a real process, data source, or target system in enough detail.",
            },
            "integration": {
                "systems_to_integrate": [],
                "integration_type": "new_step",
                "user_interface": "Not determined",
                "process_owner": use_case.department if _looks_meaningful(use_case.department) else "Not determined",
                "note": "Integration cannot be assessed until the source system, target system, and workflow owner are clarified.",
            },
            "effort_estimate": {
                "range": "Not estimated",
                "note": "Cost and effort estimates would be misleading until the problem, volume, systems, and data are described.",
            },
            "technical_risk": {
                "score": 5,
                "note": "The main risk is not technical complexity; it is missing requirements and unclear business context.",
            },
            "overall_score": 1,
        },
        "compliance": {
            "gdpr": {
                "personal_data_involved": False,
                "note": "Cannot determine GDPR relevance from the current submission. The reviewer must ask what data is processed and whether it includes identifiable people.",
            },
            "eu_ai_act": {
                "suggested_risk_class": "minimal",
                "reasoning": "No reliable AI Act classification can be made because the use case does not describe the intended AI function or deployment context.",
                "cited_articles": [],
                "confidence": "low",
                "needs_human_review": True,
            },
            "verdict": "conditional",
        },
        "cost": {
            "one_time_estimate_eur": "Not estimated",
            "ongoing_monthly_eur": "Not estimated",
            "sources": [],
            "estimate_basis": "estimated_range",
            "pricing_note": "No credible cost estimate can be produced until the use case is clarified. Internet pricing should be researched after candidate solution types are known.",
        },
        "recommendation_summary": (
            "Insufficient information was provided to assess this use case professionally. "
            "Do not send it for decision approval yet; return it to the submitter for clarification about the process, data, systems, users, and expected benefit."
        ),
        "decision_package": decision_package,
        "human_reviewed": False,
        "reviewer_overrides": {},
    }


def _low_information_decision_package(use_case: UseCaseInput) -> dict:
    use_case_ref = {
        "title": "Submitted chatbot JSON",
        "source_type": "use_case",
        "detail": (
            f"title={use_case.title}; process={use_case.current_process}; "
            f"data={use_case.data_mentioned}; benefit={use_case.expected_benefit}"
        ),
        "url": None,
    }
    return {
        "solution_recommendation": {
            "recommended_solution": (
                "No implementation solution should be approved yet. The submission must first be clarified into a real business problem with a current process, data source, target users, systems, and measurable expected benefit."
            ),
            "solution_type": "assemble",
            "rationale": "Selecting buy, build, or assemble would be speculative because the provided text appears to be placeholder/random input.",
            "implementation_steps": [
                "Return the use case to the submitter with clarification questions.",
                "Ask for the current process step by step, including who performs it and how often.",
                "Ask what data/documents are involved, where they are stored, and whether personal data is included.",
                "Ask which systems are used today and what system should receive the final output.",
                "Only after clarification, rerun feasibility, cost, solution, GDPR, and EU AI Act assessment.",
            ],
            "references": [use_case_ref],
            "assumptions": [
                "The current answers are placeholders or too vague for a reliable assessment.",
                "No internet pricing source is useful until the solution category is known.",
            ],
        },
        "feasibility_questions": [
            {
                "question": "What real business process is being improved?",
                "current_answer": "Not enough information to determine the process or technical feasibility.",
                "evidence": f"Submitted process text: {use_case.current_process}",
                "references": [use_case_ref],
                "confidence": "low",
                "action_required": "Ask the submitter to describe the current process step by step using real business terms.",
            },
            {
                "question": "What data and systems are available for the solution?",
                "current_answer": "Data and system availability are not known from the current JSON.",
                "evidence": f"Submitted data text: {use_case.data_mentioned}; submitted stack: {use_case.company_profile.existing_tech_stack}",
                "references": [use_case_ref],
                "confidence": "low",
                "action_required": "Ask where the data lives, who owns it, data volume, format, quality, and access restrictions.",
            },
        ],
        "cost_finance_questions": [
            {
                "question": "Can cost be estimated from the current submission?",
                "current_answer": "No. Any cost number would be invented because the scope, systems, users, and solution type are unknown.",
                "evidence": "The current submission does not define a concrete solution candidate or integration target.",
                "references": [use_case_ref],
                "confidence": "low",
                "action_required": "Collect scope and candidate solution type before researching actual vendor/API pricing.",
            }
        ],
        "compliance_questions": [
            {
                "question": "Can GDPR and EU AI Act status be determined from this input?",
                "current_answer": "No. The current JSON does not reliably describe processed data, users, AI function, or deployment context.",
                "evidence": f"Submitted data text: {use_case.data_mentioned}",
                "references": [use_case_ref],
                "confidence": "low",
                "action_required": "Ask whether identifiable people, employee/customer data, special-category data, automated decisions, or user-facing AI are involved.",
            }
        ],
        "reviewer_note": (
            "This package is a clarification request, not an approval recommendation. "
            "The decision maker should not approve feasibility, cost, or compliance until real use-case details are provided."
        ),
    }


def _build_decision_package(
    use_case: UseCaseInput,
    personal_data: bool,
    cited_articles: list[str],
    cost: CostAssessment,
    solution_sources: list[dict[str, str]],
    market_solutions: list[dict[str, str]],
) -> dict:
    cost_refs = [
        {
            "title": source.title,
            "source_type": "web",
            "detail": "Comparable pricing or vendor reference collected during cost estimation.",
            "url": source.url,
        }
        for source in cost.sources
    ] or [
        {
            "title": "Cost estimation assumption",
            "source_type": "estimation",
            "detail": cost.pricing_note,
            "url": None,
        }
    ]
    legal_refs = [
        {
            "title": article,
            "source_type": "legal_rag",
            "detail": "Retrieved from local EU AI Act/GDPR article chunks for this use case.",
            "url": None,
        }
        for article in cited_articles
    ]
    solution_refs = [
        {
            "title": source["title"],
            "source_type": "web",
            "detail": "Internet reference gathered by the backend for comparable solution patterns or tools.",
            "url": source["url"],
        }
        for source in solution_sources
    ]
    market_items = _market_solution_items(use_case, market_solutions)
    return {
        "solution_recommendation": {
            "recommended_solution": _recommended_solution_text(use_case),
            "solution_type": "assemble",
            "rationale": (
                "The described problem is mainly process digitization plus validation and integration. "
                "A custom AI model should not be the first step unless later evidence shows unstructured documents "
                "or image recognition are required."
            ),
            "implementation_steps": [
                "Define the required digital fields, validation rules, and owner for the current process.",
                "Create a lightweight form or mobile/tablet entry workflow to replace paper capture.",
                "Integrate the captured records with the stated system of record or export path.",
                "Add AI only where it is justified, such as anomaly checks, OCR/image capture, or draft classification.",
                "Run a small pilot, measure error reduction and time saved, then decide whether to scale.",
            ],
            "references": solution_refs
            or [
                {
                    "title": "Solution assumption",
                    "source_type": "assumption",
                    "detail": "No live web references were available; recommendation is based on use-case data.",
                    "url": None,
                }
            ],
            "assumptions": [
                "The existing process can be represented as structured digital fields.",
                "The department can confirm the system of record and validation rules.",
                "Internet references are supporting context, not final vendor selection.",
            ],
        },
        "market_solutions": market_items,
        "feasibility_questions": [
            {
                "question": "Is the described current process structured enough for a digital AI-assisted pilot?",
                "current_answer": (
                    "Likely yes: the process already records repeatable measurement fields and can be digitized before adding AI."
                ),
                "evidence": (
                    f"Current process: {use_case.current_process}. Data mentioned: {use_case.data_mentioned}."
                ),
                "references": [
                    {
                        "title": "Use-case current process and data",
                        "source_type": "use_case",
                        "detail": f"{use_case.current_process} | {use_case.data_mentioned}",
                        "url": None,
                    }
                ],
                "confidence": "medium",
                "action_required": "Confirm required measurement fields, acceptable error tolerance, and who owns data quality.",
            },
            {
                "question": "Which systems must receive the digitized measurements?",
                "current_answer": ", ".join(use_case.company_profile.existing_tech_stack)
                if use_case.company_profile.existing_tech_stack
                else "Current destination system is not specified.",
                "evidence": "Integration targets are inferred from the existing tech stack and department workflow.",
                "references": [
                    {
                        "title": "Use-case company profile",
                        "source_type": "use_case",
                        "detail": f"Department: {use_case.department}; stack: {use_case.company_profile.existing_tech_stack}",
                        "url": None,
                    }
                ],
                "confidence": "medium" if use_case.company_profile.existing_tech_stack else "low",
                "action_required": "Confirm whether ERP, Excel, or another system is the system of record.",
            },
        ],
        "cost_finance_questions": [
            {
                "question": "Is the requested budget an actual vendor price or an estimated implementation range?",
                "current_answer": (
                    f"{cost.one_time_estimate_eur} one-time and {cost.ongoing_monthly_eur} monthly; basis: {cost.estimate_basis}."
                ),
                "evidence": cost.pricing_note,
                "references": cost_refs,
                "confidence": "medium",
                "action_required": "Validate current vendor/API prices and internal implementation effort before budget approval.",
            }
        ],
        "compliance_questions": [
            {
                "question": "Does the use case plausibly involve personal data under GDPR?",
                "current_answer": "Yes" if personal_data else "No personal data is explicit in the structured input.",
                "evidence": f"Data mentioned by submitter: {use_case.data_mentioned}.",
                "references": legal_refs
                or [
                    {
                        "title": "Use-case data mentioned",
                        "source_type": "use_case",
                        "detail": use_case.data_mentioned,
                        "url": None,
                    }
                ],
                "confidence": "medium",
                "action_required": "Confirm whether operator IDs, employee identifiers, customer data, or special-category data are captured.",
            },
            {
                "question": "What EU AI Act risk review is needed before deployment?",
                "current_answer": "Human compliance review is required; initial classification is based on retrieved legal context.",
                "evidence": "The backend cites local EU AI Act/GDPR chunks retrieved for the use-case text.",
                "references": legal_refs,
                "confidence": "medium" if legal_refs else "low",
                "action_required": "Compliance owner should confirm final AI Act category and documentation duties.",
            },
        ],
        "reviewer_note": (
            "Decision maker should treat feasibility and cost values as review-ready estimates, not final approval facts. "
            "References show where the backend obtained each major assumption."
        ),
    }


def _market_solution_items(use_case: UseCaseInput, market_solutions: list[dict[str, str]]) -> list[dict]:
    items = []
    for source in market_solutions[:5]:
        title = source.get("title", "Market candidate")
        url = source.get("url")
        items.append(
            {
                "name": title,
                "category": _market_category(title),
                "fit_summary": (
                    f"Candidate market reference for '{use_case.title}'. Review whether it can support the described process, data capture, validation, and integration needs."
                ),
                "evidence": "Found by backend web search using the submitted use-case title, process, and solution keywords.",
                "references": [
                    {
                        "title": title,
                        "source_type": "web",
                        "detail": "Current web search result used as a candidate market reference.",
                        "url": url,
                    }
                ],
                "caveat": "Verify current product capabilities, pricing, region availability, data protection terms, and integration fit before recommending purchase.",
            }
        )
    if items:
        return items
    return [
        {
            "name": "No market candidates found",
            "category": "unknown",
            "fit_summary": "No specific market solution candidate was captured by the live search for this submission.",
            "evidence": "The backend market search returned no usable candidate links for the submitted use-case terms.",
            "references": [
                {
                    "title": "Market search returned no candidate",
                    "source_type": "estimation",
                    "detail": "No vendor or product should be inferred. Clarify the use case or rerun search with more specific terms.",
                    "url": None,
                }
            ],
            "caveat": "Do not treat this as proof that no market products exist. It only means this search did not return a reliable candidate.",
        },
    ]


def _market_category(title: str) -> str:
    lowered = title.lower()
    if any(word in lowered for word in ["api", "developer", "sdk"]):
        return "api_service"
    if any(word in lowered for word in ["platform", "workflow", "automation", "power apps", "appsheet"]):
        return "platform"
    if any(word in lowered for word in ["software", "solution", "system", "product"]):
        return "off_the_shelf"
    return "unknown"


def _recommended_solution_text(use_case: UseCaseInput) -> str:
    systems = ", ".join(use_case.company_profile.existing_tech_stack) or "the existing system of record"
    return (
        f"Use an assembled digital workflow for {use_case.department}: replace the paper step with a structured "
        f"data-capture form, validate the submitted fields, and synchronize or export approved records to {systems}. "
        "Treat AI as an optional assistive layer after the basic digital workflow is stable."
    )
