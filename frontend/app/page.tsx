'use client';

import { FormEvent, useState } from 'react';

type MedicationOrder = {
  name: string;
  dose: string;
  start_today?: boolean;
};

type LabOrder = {
  name: string;
  due_in_days: number;
};

type Citation = {
  type: string;
  id?: string;
  org?: string;
  year?: number;
};

type TrialMatch = {
  title?: string;
  nct_id?: string;
  site_distance_km?: number;
  status?: string;
  why_match?: string;
};

type PlanCard = {
  recommendation: string;
  rationale: string;
  alternatives: string[];
  safety_checks: string[];
  orders: {
    medication: MedicationOrder;
    labs: LabOrder[];
  };
  citations: Citation[];
  trial_matches: TrialMatch[];
  evidence_highlights?: string[];
  llm_model?: string;
  generated_at?: string;
  notes?: string;
};

type LabResponse = {
  patient_id: string;
  labs: Array<{
    name: string;
    value: number;
    unit: string;
    collected_at?: string;
    date?: string;
  }>;
};

type EvidenceResponse = {
  evidence_pack: {
    trials: TrialMatch[];
    analyses: Array<{
      trial_title: string;
      pico_grade: string;
      overall_summary: string;
    }>;
    llm_model?: string;
    generated_at?: string;
    notes?: string;
  };
};

type PlanResponse = {
  patient_id: string;
  plan_card: PlanCard;
};

const PATIENT_FALLBACK_ID = '12873';

type StatusEntry = {
  agent: string;
  message: string;
  timestamp: string;
  tone: 'info' | 'success' | 'error';
};

const DEFAULT_QUESTION =
  'Mrs. J is a 62 y/o with T2D + CKD stage 3 on metformin. Suggest the safest add-on, check contraindications, outline monitoring, and surface any local trials she might qualify for.';

const formatDate = (value?: string) => {
  if (!value) return 'n/a';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleDateString();
};

const formatTimestamp = (iso: string) => {
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

const derivePatientId = (prompt: string): string => {
  const numeric = prompt.match(/\bpatient(?:\s*(?:id|#))?\s*(\d{3,})\b/i);
  if (numeric?.[1]) {
    return numeric[1];
  }
  const standalone = prompt.match(/\b(\d{5,})\b/);
  if (standalone?.[1]) {
    return standalone[1];
  }
  return PATIENT_FALLBACK_ID;
};

const examplePrompts = [
  {
    title: 'Medication Optimization',
    prompt:
      'For Mr. K with uncontrolled T2D on basal insulin, what are the safest GLP-1 options and monitoring steps?',
  },
  {
    title: 'Renal Safety Check',
    prompt:
      'My CKD stage 4 patient is on empagliflozin. Flag any contraindications and outline next renal labs.',
  },
  {
    title: 'Trial Finder',
    prompt:
      'Locate recruiting cardiometabolic trials within 50 miles for Ms. R (T2D, obesity, ASCVD).',
  },
  {
    title: 'Medication Transition',
    prompt:
      'I want to step Mrs. S off sulfonylurea to an SGLT2 inhibitor—confirm coverage gaps and surveillance.',
  },
];

const renderList = (items?: string[]) => {
  if (!items || items.length === 0) {
    return <p className="muted">None</p>;
  }

  return (
    <ul>
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
};

export default function HomePage() {
  const [prompt, setPrompt] = useState(DEFAULT_QUESTION);
  const [resolvedPatientId, setResolvedPatientId] = useState<string | null>(null);
  const [planCard, setPlanCard] = useState<PlanCard | null>(null);
  const [labs, setLabs] = useState<LabResponse | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'plan' | 'labs' | 'evidence'>('plan');
  const [statusBanner, setStatusBanner] = useState<string>('');
  const [statusTone, setStatusTone] = useState<'info' | 'success' | 'error'>('info');
  const [statusLog, setStatusLog] = useState<StatusEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isEvidenceLoading, setEvidenceLoading] = useState(false);

  const pushStatus = (agent: string, message: string, tone: 'info' | 'success' | 'error' = 'info') => {
    const entry: StatusEntry = {
      agent,
      message,
      timestamp: new Date().toISOString(),
      tone,
    };
    setStatusBanner(`${agent}: ${message}`);
    setStatusTone(tone);
    setStatusLog((prev) => [...prev.slice(-9), entry]);
  };

  const fetchLabs = async (id: string) => {
    const response = await fetch(
      `/api/labs?patientId=${encodeURIComponent(id)}&names=eGFR,A1c&last_n=6`,
    );

    if (!response.ok) {
      throw new Error('Unable to load labs');
    }

    const data: LabResponse = await response.json();
    setLabs(data);
    pushStatus('EHR MCP', 'Latest labs retrieved', 'success');
  };

  const fetchEvidence = async (id: string) => {
    setEvidenceLoading(true);
    pushStatus('Evidence Agent', 'Fetching evidence pack…');

    try {
      setResolvedPatientId(id);
      const response = await fetch('/api/evidence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: id,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || 'Evidence Agent error');
      }

      const data: EvidenceResponse = await response.json();
      setEvidence(data);
      setActiveTab('evidence');
      pushStatus('Evidence Agent', 'Evidence pack ready.', 'success');
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Unable to fetch evidence';
      pushStatus('Evidence Agent', message, 'error');
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setStatusLog([]);
    setStatusBanner('');
    const patientId = derivePatientId(prompt);
    setResolvedPatientId(patientId);
    pushStatus('NovigiHealth Planner', `Reviewing request for patient ${patientId}…`);
    pushStatus('Care-Plan Agent', 'Contacting orchestrator…');
    setPlanCard(null);
    setLabs(null);

    try {
      const response = await fetch('/api/care-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'dr_patel',
          patient_id: patientId,
          question: prompt,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || 'Care-Plan Agent error');
      }
      pushStatus('Care-Plan Agent', 'Synthesizing recommendation…');

      const data: PlanResponse = await response.json();
      setPlanCard(data.plan_card);
      setActiveTab('plan');
      pushStatus('Care-Plan Agent', 'Plan card generated.', 'success');

      try {
        await fetchLabs(patientId);
      } catch (labError: unknown) {
        console.error(labError);
        const message = labError instanceof Error ? labError.message : 'Unable to load labs';
        pushStatus('EHR MCP', message, 'error');
      }
      pushStatus('NovigiHealth Planner', `Resolved patient context as ${patientId}.`, 'info');
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Something went wrong';
      pushStatus('System', message, 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main>
      <header>
        <div className="brand-banner">
          <div className="brand-mark">NovigiHealth</div>
          <div>
            <h1>Care Intelligence Studio</h1>
            <p>
              Orchestrate dynamic agents that blend EHR insights, real-world trials, and guarded
              LLM reasoning to support every visit.
            </p>
          </div>
        </div>
        <p className="muted">
          Tip: Ask about next-line therapies, contraindications, monitoring plans, or trial
          qualification—NovigiHealth agents will coordinate the right MCP tools automatically.
        </p>
      </header>

      <section className="card prompt-card">
        <h2>What can I ask?</h2>
        <p className="muted">
          NovigiHealth supports complex care planning, trial discovery, and safety surveillance. Try
          one of these prompts or craft your own.
        </p>
        <div className="prompt-grid">
          {examplePrompts.map((item) => (
            <div key={item.title} className="prompt-item">
              <h3>{item.title}</h3>
              <p>{item.prompt}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>Ask NovigiHealth</h2>
        <p className="muted">
          Describe the patient and what you need. The NovigiHealth agents will discover MCP tools,
          gather evidence, and synthesize an answer.
        </p>
        <form onSubmit={handleSubmit}>
          <label htmlFor="prompt">
            What would you like the agents to do?
            <textarea
              id="prompt"
              name="prompt"
              rows={4}
              value={prompt}
              placeholder="Example: For my 68 y/o with CKD stage 3 on metformin, propose escalation, check contraindications, and surface nearby SGLT2 trials."
              onChange={(event) => setPrompt(event.target.value)}
              required
            />
          </label>

          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Working…' : 'Run NovigiHealth Agents'}
          </button>
        </form>
        {statusBanner ? (
          <div className={`status-banner ${statusTone}`}>
            <span>{statusBanner}</span>
          </div>
        ) : null}
        {statusLog.length > 0 ? (
          <div className="status-timeline">
            <h3>Live Agent Timeline</h3>
            <ul>
              {statusLog.map((entry, index) => (
                <li key={`${entry.timestamp}-${index}`} className={`status-item ${entry.tone}`}>
                  <div className="status-meta">
                    <span className="status-agent">{entry.agent}</span>
                    <span className="status-time">{formatTimestamp(entry.timestamp)}</span>
                  </div>
                  <p>{entry.message}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="tab-bar">
          <button
            type="button"
            className={activeTab === 'plan' ? 'active' : ''}
            onClick={() => setActiveTab('plan')}
            disabled={!planCard}
          >
            Plan Card
          </button>
          <button
            type="button"
            className={activeTab === 'labs' ? 'active' : ''}
            onClick={() => setActiveTab('labs')}
            disabled={!labs}
          >
            Labs
          </button>
          <button
            type="button"
            className={activeTab === 'evidence' ? 'active' : ''}
            onClick={() => setActiveTab('evidence')}
            disabled={!evidence && !planCard}
          >
            Evidence
          </button>
          <button
            type="button"
            onClick={() => {
              const id = resolvedPatientId ?? PATIENT_FALLBACK_ID;
              fetchEvidence(id);
            }}
            disabled={isEvidenceLoading}
          >
            {isEvidenceLoading ? 'Loading evidence…' : 'Refresh evidence tab'}
          </button>
        </div>

        {activeTab === 'plan' && (
          <div>
            {planCard ? (
              <article>
                <section className="plan-section">
                  <h3>Recommendation</h3>
                  <p>{planCard.recommendation}</p>
                  <p className="muted">{planCard.rationale}</p>
                  {resolvedPatientId ? (
                    <p className="muted">
                      Working patient context: <strong>{resolvedPatientId}</strong>
                    </p>
                  ) : null}
                  {planCard.llm_model ? (
                    <p className="muted">
                      Generated with {planCard.llm_model}{' '}
                      {planCard.generated_at ? `on ${formatDate(planCard.generated_at)}` : ''}
                    </p>
                  ) : null}
                  {planCard.notes ? <p className="muted">{planCard.notes}</p> : null}
                </section>

                <section className="plan-section">
                  <h3>Alternatives</h3>
                  {renderList(planCard.alternatives)}
                </section>

                <section className="plan-section">
                  <h3>Safety Checks</h3>
                  {renderList(planCard.safety_checks)}
                </section>

                <section className="plan-section">
                  <h3>Orders</h3>
                  <div className="badge">Medication</div>
                  <p>
                    {planCard.orders.medication.name} — {planCard.orders.medication.dose}
                  </p>
                  <div className="badge">Labs</div>
                  {renderList(
                    planCard.orders.labs.map(
                      (lab) => `${lab.name} due in ${lab.due_in_days} days`,
                    ),
                  )}
                </section>

                <section className="plan-section">
                  <h3>Citations</h3>
                  {renderList(
                    planCard.citations.map((citation) => {
                      const label = citation.id || citation.org || 'Unknown';
                      const year = citation.year ?? 'n/a';
                      return `${citation.type}: ${label} (${year})`;
                    }),
                  )}
                </section>

                <section className="plan-section">
                  <h3>Trial Matches</h3>
                  {planCard.trial_matches && planCard.trial_matches.length > 0 ? (
                    <ul>
                      {planCard.trial_matches.map((trial, index) => (
                        <li key={`${trial.nct_id}-${index}`}>
                          <strong>{trial.title || 'Unnamed trial'}</strong>{' '}
                          ({trial.nct_id || 'NCT pending'}) — {trial.status || 'status n/a'} —
                          {' '}
                          {trial.site_distance_km != null
                            ? `${trial.site_distance_km.toFixed(1)} km`
                            : 'distance n/a'}
                          <br />
                          <span className="muted">{trial.why_match}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No trials recommended yet.</p>
                  )}
                </section>

                {planCard.evidence_highlights && planCard.evidence_highlights.length > 0 ? (
                  <section className="plan-section">
                    <h3>Evidence Highlights</h3>
                    {renderList(planCard.evidence_highlights)}
                  </section>
                ) : null}
              </article>
            ) : (
              <p className="muted">Request a plan to view the generated card.</p>
            )}
          </div>
        )}

        {activeTab === 'labs' && (
          <div>
            {labs && labs.labs.length > 0 ? (
              <div className="lab-grid">
                {labs.labs.map((lab, index) => (
                  <div key={`${lab.name}-${index}`} className="lab-item">
                    <h4>{lab.name}</h4>
                    <p>
                      <strong>{lab.value}</strong> {lab.unit}
                    </p>
                    <p className="muted">{formatDate(lab.collected_at || lab.date)}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">No lab data yet — request a plan or try again.</p>
            )}
          </div>
        )}

        {activeTab === 'evidence' && (
          <div>
            {evidence ? (
              <>
                <section className="plan-section">
                  <h3>Nearby / Relevant Trials</h3>
                  {resolvedPatientId ? (
                    <p className="muted">
                      Patient context: <strong>{resolvedPatientId}</strong>
                    </p>
                  ) : null}
                  {evidence.evidence_pack.llm_model ? (
                    <p className="muted">
                      Evidence graded with {evidence.evidence_pack.llm_model}{' '}
                      {evidence.evidence_pack.generated_at
                        ? `on ${formatDate(evidence.evidence_pack.generated_at)}`
                        : ''}
                    </p>
                  ) : null}
                  {evidence.evidence_pack.notes ? (
                    <p className="muted">{evidence.evidence_pack.notes}</p>
                  ) : null}
                  {evidence.evidence_pack.trials.length ? (
                    <ul>
                      {evidence.evidence_pack.trials.map((trial, index) => (
                        <li key={`${trial.nct_id}-${index}`}>
                          <strong>{trial.title || 'Unnamed trial'}</strong>{' '}
                          ({trial.nct_id || 'NCT pending'}) — {trial.status || 'status n/a'} —
                          {' '}
                          {trial.site_distance_km != null
                            ? `${trial.site_distance_km.toFixed(1)} km`
                            : 'distance n/a'}
                          <br />
                          <span className="muted">{trial.why_match || 'Eligibility summary unavailable.'}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No trials within the configured radius.</p>
                  )}
                </section>

                <section className="plan-section">
                  <h3>Evidence Summaries</h3>
                  {evidence.evidence_pack.analyses.length ? (
                    <ul>
                      {evidence.evidence_pack.analyses.map((analysis, index) => (
                        <li key={`${analysis.trial_title}-${index}`}>
                          <strong>{analysis.trial_title}</strong> — PICO grade {analysis.pico_grade}
                          <br />
                          <span className="muted">{analysis.overall_summary}</span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">No evidence summaries available.</p>
                  )}
                </section>
              </>
            ) : (
              <p className="muted">
                Use “Refresh evidence tab” after requesting a plan to preview the Evidence Agent output.
              </p>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
