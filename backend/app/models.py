from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyProfile(BaseModel):
    industry: str
    size: str
    region: str
    existing_tech_stack: list[str]


class UseCaseInput(BaseModel):
    id: str
    title: str
    problem_description: str
    department: str
    current_process: str
    data_mentioned: str
    expected_benefit: str
    company_profile: CompanyProfile


class ChatbotAnswer(BaseModel):
    question_id: str
    answer: str = ""
    question_text: str = ""
    is_followup: bool = False


class ChatbotSessionInput(BaseModel):
    session_id: str
    status: str = ""
    category: str = ""
    department: str = ""
    answers: list[ChatbotAnswer]


class ScoreNote(BaseModel):
    score: int = Field(ge=1, le=5)
    note: str


class SolutionApproach(BaseModel):
    type: Literal["buy", "assemble", "build"]
    note: str


class IntegrationAssessment(BaseModel):
    systems_to_integrate: list[str]
    integration_type: Literal["replace", "augment", "new_step"]
    user_interface: str
    process_owner: str
    note: str


class EffortEstimate(BaseModel):
    range: str
    note: str


class FeasibilityAssessment(BaseModel):
    data_availability: ScoreNote
    solution_approach: SolutionApproach
    integration: IntegrationAssessment
    effort_estimate: EffortEstimate
    technical_risk: ScoreNote
    overall_score: float = Field(ge=1, le=5)


class GdprAssessment(BaseModel):
    personal_data_involved: bool
    note: str


class EuAiActAssessment(BaseModel):
    suggested_risk_class: Literal["minimal", "limited", "high-risk", "prohibited"]
    reasoning: str
    cited_articles: list[str]
    confidence: Literal["low", "medium", "high"]
    needs_human_review: bool


class ComplianceAssessment(BaseModel):
    gdpr: GdprAssessment
    eu_ai_act: EuAiActAssessment
    verdict: Literal["pass", "conditional", "fail"]


class CostSource(BaseModel):
    title: str
    url: str


class CostAssessment(BaseModel):
    one_time_estimate_eur: str
    ongoing_monthly_eur: str
    sources: list[CostSource]
    estimate_basis: Literal["actual_pricing", "estimated_range", "mixed"] = "estimated_range"
    pricing_note: str = "Estimated range; reviewer should validate current vendor pricing before approval."


class EvidenceReference(BaseModel):
    title: str
    source_type: Literal["use_case", "legal_rag", "web", "assumption", "estimation"]
    detail: str
    url: str | None = None


class DecisionQuestion(BaseModel):
    question: str
    current_answer: str
    evidence: str
    references: list[EvidenceReference]
    confidence: Literal["low", "medium", "high"]
    action_required: str


class SolutionRecommendation(BaseModel):
    recommended_solution: str = ""
    solution_type: Literal["buy", "assemble", "build"] = "assemble"
    rationale: str = ""
    implementation_steps: list[str] = Field(default_factory=list)
    references: list[EvidenceReference] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class MarketSolution(BaseModel):
    name: str
    category: Literal["off_the_shelf", "platform", "api_service", "custom_build_reference", "unknown"]
    fit_summary: str
    evidence: str
    references: list[EvidenceReference] = Field(default_factory=list)
    caveat: str = "Market result is a candidate reference only; reviewer must verify current pricing, availability, and fit."


class DecisionPackage(BaseModel):
    solution_recommendation: SolutionRecommendation = Field(default_factory=SolutionRecommendation)
    market_solutions: list[MarketSolution] = Field(default_factory=list)
    feasibility_questions: list[DecisionQuestion] = Field(default_factory=list)
    cost_finance_questions: list[DecisionQuestion] = Field(default_factory=list)
    compliance_questions: list[DecisionQuestion] = Field(default_factory=list)
    reviewer_note: str = "Decision maker should validate assumptions, evidence, and open actions before approval."


class AssessmentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_case_id: str
    feasibility: FeasibilityAssessment
    compliance: ComplianceAssessment
    cost: CostAssessment
    recommendation_summary: str
    decision_package: DecisionPackage = Field(default_factory=DecisionPackage)
    human_reviewed: bool = False
    reviewer_overrides: dict = Field(default_factory=dict)


class StoredAssessment(BaseModel):
    assessment: AssessmentOutput
    status: Literal["pending", "in_review", "sent"]
    source_use_case: UseCaseInput | None = None


class ConfirmRequest(BaseModel):
    reviewer_overrides: dict = Field(default_factory=dict)
