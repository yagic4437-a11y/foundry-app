export type UseCaseInput = {
  id: string;
  title: string;
  problem_description: string;
  department: string;
  current_process: string;
  data_mentioned: string;
  expected_benefit: string;
  company_profile: {
    industry: string;
    size: string;
    region: string;
    existing_tech_stack: string[];
  };
};

export type AssessmentOutput = {
  use_case_id: string;
  feasibility: {
    data_availability: ScoreNote;
    solution_approach: { type: "buy" | "assemble" | "build"; note: string };
    integration: {
      systems_to_integrate: string[];
      integration_type: "replace" | "augment" | "new_step";
      user_interface: string;
      process_owner: string;
      note: string;
    };
    effort_estimate: { range: string; note: string };
    technical_risk: ScoreNote;
    overall_score: number;
  };
  compliance: {
    gdpr: { personal_data_involved: boolean; note: string };
    eu_ai_act: {
      suggested_risk_class: "minimal" | "limited" | "high-risk" | "prohibited";
      reasoning: string;
      cited_articles: string[];
      confidence: "low" | "medium" | "high";
      needs_human_review: boolean;
    };
    verdict: "pass" | "conditional" | "fail";
  };
  cost: {
    one_time_estimate_eur: string;
    ongoing_monthly_eur: string;
    sources: { title: string; url: string }[];
    estimate_basis: "actual_pricing" | "estimated_range" | "mixed";
    pricing_note: string;
  };
  recommendation_summary: string;
  decision_package: DecisionPackage;
  human_reviewed: boolean;
  reviewer_overrides: Record<string, unknown>;
};

export type ScoreNote = {
  score: number;
  note: string;
};

export type StoredAssessment = {
  assessment: AssessmentOutput;
  status: "pending" | "in_review" | "sent";
  source_use_case?: UseCaseInput | null;
};

export type ChatbotSessionInput = {
  session_id: string;
  status?: string;
  category?: string;
  department?: string;
  answers: {
    question_id: string;
    question_text?: string;
    answer: string;
    is_followup?: boolean;
  }[];
};

export type EvidenceReference = {
  title: string;
  source_type: "use_case" | "legal_rag" | "web" | "assumption" | "estimation";
  detail: string;
  url?: string | null;
};

export type DecisionQuestion = {
  question: string;
  current_answer: string;
  evidence: string;
  references: EvidenceReference[];
  confidence: "low" | "medium" | "high";
  action_required: string;
};

export type DecisionPackage = {
  solution_recommendation: SolutionRecommendation;
  market_solutions: MarketSolution[];
  feasibility_questions: DecisionQuestion[];
  cost_finance_questions: DecisionQuestion[];
  compliance_questions: DecisionQuestion[];
  reviewer_note: string;
};

export type SolutionRecommendation = {
  recommended_solution: string;
  solution_type: "buy" | "assemble" | "build";
  rationale: string;
  implementation_steps: string[];
  references: EvidenceReference[];
  assumptions: string[];
};

export type MarketSolution = {
  name: string;
  category: "off_the_shelf" | "platform" | "api_service" | "custom_build_reference" | "unknown";
  fit_summary: string;
  evidence: string;
  references: EvidenceReference[];
  caveat: string;
};
