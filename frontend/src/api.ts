import type { AssessmentOutput, ChatbotSessionInput, StoredAssessment, UseCaseInput } from "./types";

export const sampleUseCases: UseCaseInput[] = [
  {
    id: "demo-technical-001",
    title: "AI support chatbot for technical department",
    problem_description: "Internal users wait too long for answers to recurring technical support questions.",
    department: "Technical department",
    current_process: "Employees send tickets and support staff answer repeated setup questions manually.",
    data_mentioned: "Support tickets, knowledge base articles, employee account identifiers",
    expected_benefit: "Faster answers, fewer repeated tickets, and more time for complex support tasks.",
    company_profile: {
      industry: "Software and services",
      size: "Medium",
      region: "EU",
      existing_tech_stack: ["Zendesk", "Confluence", "Slack"]
    }
  },
  {
    id: "demo-operations-002",
    title: "Digitize paper box measurements",
    problem_description: "Operators record box dimensions on paper and retype them later.",
    department: "Operations",
    current_process: "Paper forms are manually entered into ERP at the end of each shift.",
    data_mentioned: "Box dimensions, timestamps, shift identifiers",
    expected_benefit: "Reduce retyping effort and measurement mistakes.",
    company_profile: {
      industry: "Manufacturing",
      size: "Medium",
      region: "EU",
      existing_tech_stack: ["ERP", "Excel"]
    }
  }
];

export async function listAssessments(): Promise<StoredAssessment[]> {
  const response = await fetch("/assess");
  if (!response.ok) return [];
  return response.json();
}

export async function assessUseCase(useCase: UseCaseInput): Promise<AssessmentOutput> {
  const response = await fetch("/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(useCase)
  });
  if (!response.ok) throw new Error("Assessment failed");
  return response.json();
}

export async function assessChatbotSession(session: ChatbotSessionInput): Promise<AssessmentOutput> {
  const response = await fetch("/assess/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(session)
  });
  if (!response.ok) throw new Error("Chatbot session assessment failed");
  return response.json();
}

export async function confirmAssessment(
  useCaseId: string,
  reviewerOverrides: Record<string, unknown>
): Promise<StoredAssessment> {
  const response = await fetch(`/assess/${useCaseId}/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer_overrides: reviewerOverrides })
  });
  if (!response.ok) throw new Error("Confirm failed");
  return response.json();
}
