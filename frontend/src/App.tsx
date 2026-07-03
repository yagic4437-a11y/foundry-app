import { CheckCircle2, ClipboardList, RotateCw, Send, ShieldCheck, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { assessChatbotSession, assessUseCase, confirmAssessment, listAssessments, sampleUseCases } from "./api";
import type { AssessmentOutput, ChatbotSessionInput, DecisionQuestion, StoredAssessment, UseCaseInput } from "./types";

type View = "queue" | "assessment" | "confirm";

export default function App() {
  const [role, setRole] = useState("Technical reviewer");
  const [view, setView] = useState<View>("queue");
  const [stored, setStored] = useState<StoredAssessment[]>([]);
  const [selectedUseCase, setSelectedUseCase] = useState<UseCaseInput>(sampleUseCases[0]);
  const [assessment, setAssessment] = useState<AssessmentOutput | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("Backend not contacted yet.");

  useEffect(() => {
    listAssessments()
      .then((items) => {
        setStored(items);
        setNotice(items.length ? "Loaded stored assessments." : "Ready with demo use cases.");
      })
      .catch(() => setNotice("Backend unavailable; demo use cases still work once API starts."));
  }, []);

  const queue = useMemo(() => {
    const storedIds = new Set(stored.map((item) => item.assessment.use_case_id));
    const pending = sampleUseCases
      .filter((item) => !storedIds.has(item.id))
      .map((item) => ({ useCase: item, status: "pending" as const }));
    const reviewed = stored.map((item) => ({
      useCase: item.source_use_case ?? sampleUseCases.find((useCase) => useCase.id === item.assessment.use_case_id) ?? {
        ...sampleUseCases[0],
        id: item.assessment.use_case_id,
        title: item.assessment.use_case_id
      },
      status: item.status
    }));
    return [...pending, ...reviewed];
  }, [stored]);

  async function runAssessment(useCase: UseCaseInput) {
    setSelectedUseCase(useCase);
    setLoading(true);
    setNotice("Running assessment.");
    try {
      const result = await assessUseCase(useCase);
      setAssessment(result);
      setStored((current) => [
        { assessment: result, status: "in_review", source_use_case: useCase },
        ...current.filter((item) => item.assessment.use_case_id !== result.use_case_id)
      ]);
      setView("assessment");
      setNotice("Assessment ready for review.");
    } catch (error) {
      setNotice("Assessment failed. Start the FastAPI backend and try again.");
    } finally {
      setLoading(false);
    }
  }

  async function importChatbotSession(file: File | null) {
    if (!file) return;
    setLoading(true);
    setNotice("Importing chatbot JSON.");
    try {
      const session = JSON.parse(await file.text()) as ChatbotSessionInput;
      const result = await assessChatbotSession(session);
      const useCase = normalizeSessionForDisplay(session, result.use_case_id);
      setSelectedUseCase(useCase);
      setAssessment(result);
      setStored((current) => [
        { assessment: result, status: "in_review", source_use_case: useCase },
        ...current.filter((item) => item.assessment.use_case_id !== result.use_case_id)
      ]);
      setView("assessment");
      setNotice("Chatbot session assessed and added to queue.");
    } catch {
      setNotice("Could not import that chatbot JSON. Check the file shape and backend status.");
    } finally {
      setLoading(false);
    }
  }

  async function sendAssessment() {
    if (!assessment) return;
    setLoading(true);
    try {
      const result = await confirmAssessment(assessment.use_case_id, assessment.reviewer_overrides);
      setAssessment(result.assessment);
      setStored((current) => [
        result,
        ...current.filter((item) => item.assessment.use_case_id !== result.assessment.use_case_id)
      ]);
      setNotice("Sent to decision maker.");
      setView("queue");
    } catch {
      setNotice("Send failed. Check backend status.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f8fa]">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-950">AI Use-Case Assessment Hub</h1>
            <p className="mt-1 text-sm text-slate-600">Technical feasibility, integration, cost, GDPR, and EU AI Act review</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              className="h-10 rounded border border-slate-300 bg-white px-3 text-sm"
              value={role}
              onChange={(event) => setRole(event.target.value)}
            >
              <option>Technical reviewer</option>
              <option>Compliance reviewer</option>
            </select>
            <div className="rounded border border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-700">{role}</div>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-5 py-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <nav className="flex rounded border border-slate-300 bg-white p-1 text-sm">
            {(["queue", "assessment", "confirm"] as View[]).map((item) => (
              <button
                key={item}
                className={`rounded px-3 py-2 capitalize ${view === item ? "bg-slate-900 text-white" : "text-slate-700"}`}
                onClick={() => setView(item)}
              >
                {item}
              </button>
            ))}
          </nav>
          <div className="flex flex-wrap items-center gap-3">
            <label className="inline-flex h-10 cursor-pointer items-center gap-2 rounded border border-slate-300 bg-white px-3 text-sm font-medium text-slate-800">
              <Upload className="h-4 w-4" />
              Import chatbot JSON
              <input
                className="hidden"
                type="file"
                accept="application/json,.json"
                disabled={loading}
                onChange={(event) => {
                  void importChatbotSession(event.target.files?.[0] ?? null);
                  event.currentTarget.value = "";
                }}
              />
            </label>
            <div className="text-sm text-slate-600">{notice}</div>
          </div>
        </div>

        {view === "queue" && (
          <section className="overflow-hidden rounded border border-slate-200 bg-white">
            <div className="grid grid-cols-[1.4fr_1fr_120px_140px] gap-4 border-b border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-600 max-lg:grid-cols-1">
              <span>Use case</span>
              <span>Department</span>
              <span>Status</span>
              <span>Action</span>
            </div>
            {queue.map((item) => (
              <div
                key={item.useCase.id}
                className="grid grid-cols-[1.4fr_1fr_120px_140px] gap-4 border-b border-slate-100 px-4 py-4 last:border-b-0 max-lg:grid-cols-1"
              >
                <div>
                  <div className="font-medium text-slate-950">{item.useCase.title}</div>
                  <div className="mt-1 text-sm text-slate-600">{item.useCase.problem_description}</div>
                </div>
                <div className="text-sm text-slate-700">{item.useCase.department}</div>
                <StatusBadge status={item.status} />
                <button
                  className="inline-flex h-10 items-center justify-center gap-2 rounded bg-slate-900 px-3 text-sm font-medium text-white disabled:opacity-50"
                  disabled={loading}
                  onClick={() => runAssessment(item.useCase)}
                  title="Run or reopen assessment"
                >
                  {loading ? <RotateCw className="h-4 w-4 animate-spin" /> : <ClipboardList className="h-4 w-4" />}
                  Assess
                </button>
              </div>
            ))}
          </section>
        )}

        {view === "assessment" && assessment && (
          <AssessmentEditor
            useCase={selectedUseCase}
            assessment={assessment}
            setAssessment={setAssessment}
            onConfirm={() => setView("confirm")}
          />
        )}

        {view === "confirm" && assessment && (
          <section className="rounded border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-950">Review summary</h2>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">{assessment.recommendation_summary}</p>
              </div>
              <ShieldCheck className="h-6 w-6 text-emerald-700" />
            </div>
            <dl className="mt-5 grid gap-3 md:grid-cols-3">
              <Metric label="Overall score" value={assessment.feasibility.overall_score.toFixed(1)} />
              <Metric label="AI Act class" value={assessment.compliance.eu_ai_act.suggested_risk_class} />
              <Metric label="Compliance verdict" value={assessment.compliance.verdict} />
            </dl>
            <DecisionPackageView assessment={assessment} compact />
            <button
              className="mt-6 inline-flex h-11 items-center gap-2 rounded bg-emerald-700 px-4 text-sm font-medium text-white disabled:opacity-50"
              disabled={loading}
              onClick={sendAssessment}
            >
              <Send className="h-4 w-4" />
              Send to decision maker
            </button>
          </section>
        )}
      </div>
    </main>
  );
}

function AssessmentEditor({
  useCase,
  assessment,
  setAssessment,
  onConfirm
}: {
  useCase: UseCaseInput;
  assessment: AssessmentOutput;
  setAssessment: (assessment: AssessmentOutput) => void;
  onConfirm: () => void;
}) {
  const update = (next: Partial<AssessmentOutput>) => setAssessment({ ...assessment, ...next });
  return (
    <div className="grid gap-5 lg:grid-cols-[340px_1fr]">
      <aside className="rounded border border-slate-200 bg-white p-4">
        <h2 className="font-semibold text-slate-950">{useCase.title}</h2>
        <div className="mt-3 space-y-3 text-sm text-slate-700">
          <p>{useCase.problem_description}</p>
          <Field label="Current process" value={useCase.current_process} />
          <Field label="Data" value={useCase.data_mentioned} />
          <Field label="Benefit" value={useCase.expected_benefit} />
        </div>
      </aside>
      <section className="space-y-4">
        <EditableBlock
          title="Data availability"
          score={assessment.feasibility.data_availability.score}
          note={assessment.feasibility.data_availability.note}
          onScore={(score) =>
            update({
              feasibility: {
                ...assessment.feasibility,
                data_availability: { ...assessment.feasibility.data_availability, score }
              }
            })
          }
          onNote={(note) =>
            update({
              feasibility: {
                ...assessment.feasibility,
                data_availability: { ...assessment.feasibility.data_availability, note }
              }
            })
          }
        />
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-950">Solution approach</h3>
          <select
            className="mt-3 h-10 rounded border border-slate-300 px-3 text-sm"
            value={assessment.feasibility.solution_approach.type}
            onChange={(event) =>
              update({
                feasibility: {
                  ...assessment.feasibility,
                  solution_approach: {
                    ...assessment.feasibility.solution_approach,
                    type: event.target.value as AssessmentOutput["feasibility"]["solution_approach"]["type"]
                  }
                }
              })
            }
          >
            <option value="buy">buy</option>
            <option value="assemble">assemble</option>
            <option value="build">build</option>
          </select>
          <Textarea
            value={assessment.feasibility.solution_approach.note}
            onChange={(note) =>
              update({
                feasibility: {
                  ...assessment.feasibility,
                  solution_approach: { ...assessment.feasibility.solution_approach, note }
                }
              })
            }
          />
        </div>
        <EditableBlock
          title="Technical risk"
          score={assessment.feasibility.technical_risk.score}
          note={assessment.feasibility.technical_risk.note}
          onScore={(score) =>
            update({
              feasibility: {
                ...assessment.feasibility,
                technical_risk: { ...assessment.feasibility.technical_risk, score }
              }
            })
          }
          onNote={(note) =>
            update({
              feasibility: {
                ...assessment.feasibility,
                technical_risk: { ...assessment.feasibility.technical_risk, note }
              }
            })
          }
        />
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-950">Compliance</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <select
              className="h-10 rounded border border-slate-300 px-3 text-sm"
              value={assessment.compliance.eu_ai_act.suggested_risk_class}
              onChange={(event) =>
                update({
                  compliance: {
                    ...assessment.compliance,
                    eu_ai_act: {
                      ...assessment.compliance.eu_ai_act,
                      suggested_risk_class: event.target.value as AssessmentOutput["compliance"]["eu_ai_act"]["suggested_risk_class"]
                    }
                  }
                })
              }
            >
              <option value="minimal">minimal</option>
              <option value="limited">limited</option>
              <option value="high-risk">high-risk</option>
              <option value="prohibited">prohibited</option>
            </select>
            <Metric label="Confidence" value={assessment.compliance.eu_ai_act.confidence} />
            <Metric label="GDPR data" value={assessment.compliance.gdpr.personal_data_involved ? "yes" : "no"} />
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">{assessment.compliance.eu_ai_act.reasoning}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {assessment.compliance.eu_ai_act.cited_articles.map((article) => (
              <span key={article} className="rounded border border-slate-300 bg-slate-50 px-2 py-1 text-xs text-slate-700">
                {article}
              </span>
            ))}
          </div>
        </div>
        <div className="rounded border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-950">Cost and recommendation</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <Input
              label="One-time estimate"
              value={assessment.cost.one_time_estimate_eur}
              onChange={(value) => update({ cost: { ...assessment.cost, one_time_estimate_eur: value } })}
            />
            <Input
              label="Monthly estimate"
              value={assessment.cost.ongoing_monthly_eur}
              onChange={(value) => update({ cost: { ...assessment.cost, ongoing_monthly_eur: value } })}
            />
          </div>
          <div className="mt-3 space-y-1 text-sm">
            {assessment.cost.sources.map((source) => (
              <a key={source.url} href={source.url} target="_blank" className="block text-sky-700 underline">
                {source.title}
              </a>
            ))}
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">
            Basis: <span className="font-medium">{assessment.cost.estimate_basis}</span>. {assessment.cost.pricing_note}
          </p>
          <Textarea
            value={assessment.recommendation_summary}
            onChange={(recommendation_summary) => update({ recommendation_summary })}
          />
        </div>
        <DecisionPackageView assessment={assessment} />
        <button className="inline-flex h-11 items-center gap-2 rounded bg-slate-900 px-4 text-sm font-medium text-white" onClick={onConfirm}>
          <CheckCircle2 className="h-4 w-4" />
          Review confirm screen
        </button>
      </section>
    </div>
  );
}

function normalizeSessionForDisplay(session: ChatbotSessionInput, useCaseId: string): UseCaseInput {
  const answers = session.answers.reduce<Record<string, string[]>>((acc, item) => {
    const value = item.answer?.trim();
    if (!value) return acc;
    acc[item.question_id] = [...(acc[item.question_id] ?? []), value];
    return acc;
  }, {});
  const getAnswer = (questionId: string) => (answers[questionId] ?? []).join("\n");
  const tools = getAnswer("tools_systems")
    .replace(/;/g, ",")
    .split(",")
    .map((item: string) => item.trim())
    .filter(Boolean);
  const description = getAnswer("description_problem");
  return {
    id: useCaseId,
    title: getAnswer("title") || session.category || useCaseId,
    problem_description: description || "No problem description was provided.",
    department: getAnswer("department") || session.department || "Unknown department",
    current_process: description || "Current process was not described.",
    data_mentioned: getAnswer("data_involved"),
    expected_benefit: getAnswer("goal"),
    company_profile: {
      industry: "Not specified",
      size: "Not specified",
      region: "EU",
      existing_tech_stack: tools
    }
  };
}

function DecisionPackageView({ assessment, compact = false }: { assessment: AssessmentOutput; compact?: boolean }) {
  const packageItems = [
    { title: "Feasibility questions", items: assessment.decision_package.feasibility_questions },
    { title: "Cost and finance questions", items: assessment.decision_package.cost_finance_questions },
    { title: "Compliance questions", items: assessment.decision_package.compliance_questions }
  ];
  return (
    <section className={compact ? "mt-5 border-t border-slate-200 pt-5" : "rounded border border-slate-200 bg-white p-4"}>
      <h3 className="font-medium text-slate-950">Decision-maker package</h3>
      <p className="mt-2 text-sm leading-6 text-slate-700">{assessment.decision_package.reviewer_note}</p>
      <SolutionRecommendationView assessment={assessment} />
      <MarketSolutionsView assessment={assessment} />
      <div className="mt-4 grid gap-4">
        {packageItems.map((group) => (
          <div key={group.title}>
            <h4 className="text-sm font-semibold text-slate-900">{group.title}</h4>
            <div className="mt-2 grid gap-3">
              {group.items.map((item, index) => (
                <DecisionQuestionCard key={`${group.title}-${index}`} item={item} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function MarketSolutionsView({ assessment }: { assessment: AssessmentOutput }) {
  const marketSolutions = assessment.decision_package.market_solutions ?? [];
  if (!marketSolutions.length) return null;
  return (
    <section className="mt-4">
      <h4 className="text-sm font-semibold text-slate-900">Market alternatives</h4>
      <div className="mt-2 grid gap-3">
        {marketSolutions.map((item, index) => (
          <article key={`${item.name}-${index}`} className="rounded border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <h5 className="max-w-3xl text-sm font-semibold text-slate-950">{item.name}</h5>
              <span className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700">
                {item.category}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-700">{item.fit_summary}</p>
            <p className="mt-2 text-xs leading-5 text-slate-600">Evidence: {item.evidence}</p>
            <p className="mt-2 text-xs leading-5 text-slate-600">Caveat: {item.caveat}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {item.references.map((reference, refIndex) =>
                reference.url ? (
                  <a
                    key={`${reference.title}-${refIndex}`}
                    href={reference.url}
                    target="_blank"
                    className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 underline"
                  >
                    {reference.title}
                  </a>
                ) : (
                  <span key={`${reference.title}-${refIndex}`} className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
                    {reference.source_type}: {reference.title}
                  </span>
                )
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function SolutionRecommendationView({ assessment }: { assessment: AssessmentOutput }) {
  const solution = assessment.decision_package.solution_recommendation;
  if (!solution.recommended_solution) return null;
  return (
    <article className="mt-4 rounded border border-emerald-200 bg-emerald-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm font-semibold text-slate-950">Recommended solution</h4>
        <span className="rounded border border-emerald-300 bg-white px-2 py-1 text-xs font-medium text-emerald-800">
          {solution.solution_type}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-800">{solution.recommended_solution}</p>
      <p className="mt-2 text-xs leading-5 text-slate-700">Rationale: {solution.rationale}</p>
      <ol className="mt-2 list-decimal space-y-1 pl-5 text-xs leading-5 text-slate-700">
        {solution.implementation_steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <div className="mt-2 flex flex-wrap gap-2">
        {solution.references.map((reference, index) =>
          reference.url ? (
            <a
              key={`${reference.title}-${index}`}
              href={reference.url}
              target="_blank"
              className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 underline"
            >
              {reference.title}
            </a>
          ) : (
            <span key={`${reference.title}-${index}`} className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
              {reference.source_type}: {reference.title}
            </span>
          )
        )}
      </div>
    </article>
  );
}

function DecisionQuestionCard({ item }: { item: DecisionQuestion }) {
  return (
    <article className="rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h5 className="max-w-3xl text-sm font-semibold text-slate-950">{item.question}</h5>
        <span className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700">
          {item.confidence}
        </span>
      </div>
      <p className="mt-2 text-sm leading-6 text-slate-700">{item.current_answer}</p>
      <p className="mt-2 text-xs leading-5 text-slate-600">Evidence: {item.evidence}</p>
      <p className="mt-2 text-xs leading-5 text-slate-600">Action: {item.action_required}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {item.references.map((reference, index) =>
          reference.url ? (
            <a
              key={`${reference.title}-${index}`}
              href={reference.url}
              target="_blank"
              className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 underline"
            >
              {reference.title}
            </a>
          ) : (
            <span key={`${reference.title}-${index}`} className="rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700">
              {reference.source_type}: {reference.title}
            </span>
          )
        )}
      </div>
    </article>
  );
}

function EditableBlock({
  title,
  score,
  note,
  onScore,
  onNote
}: {
  title: string;
  score: number;
  note: string;
  onScore: (score: number) => void;
  onNote: (note: string) => void;
}) {
  return (
    <div className="rounded border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-4">
        <h3 className="font-medium text-slate-950">{title}</h3>
        <input
          className="h-10 w-20 rounded border border-slate-300 px-3 text-sm"
          min={1}
          max={5}
          type="number"
          value={score}
          onChange={(event) => onScore(Number(event.target.value))}
        />
      </div>
      <Textarea value={note} onChange={onNote} />
    </div>
  );
}

function Textarea({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <textarea
      className="mt-3 min-h-24 w-full resize-y rounded border border-slate-300 px-3 py-2 text-sm leading-6"
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function Input({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="block text-sm text-slate-700">
      <span className="font-medium text-slate-800">{label}</span>
      <input
        className="mt-2 h-10 w-full rounded border border-slate-300 px-3 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1">{value}</div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-950">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const classes =
    status === "sent"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : status === "in_review"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-slate-200 bg-slate-50 text-slate-700";
  return <span className={`inline-flex h-8 w-fit items-center rounded border px-2 text-xs font-medium ${classes}`}>{status}</span>;
}
