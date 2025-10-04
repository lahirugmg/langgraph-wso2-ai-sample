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

const DEFAULT_QUESTION =
  'Add-on to metformin for T2D with CKD stage 3; show supporting evidence and local recruiting trials.';

const formatDate = (value?: string) => {
  if (!value) return 'n/a';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleDateString();
};

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
  const [patientId, setPatientId] = useState('12873');
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [planCard, setPlanCard] = useState<PlanCard | null>(null);
  const [labs, setLabs] = useState<LabResponse | null>(null);
  const [evidence, setEvidence] = useState<EvidenceResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'plan' | 'labs' | 'evidence'>('plan');
  const [status, setStatus] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [isEvidenceLoading, setEvidenceLoading] = useState(false);

  const fetchLabs = async (id: string) => {
    const response = await fetch(
      `/api/labs?patientId=${encodeURIComponent(id)}&names=eGFR,A1c&last_n=6`,
    );

    if (!response.ok) {
      throw new Error('Unable to load labs');
    }

    const data: LabResponse = await response.json();
    setLabs(data);
  };

  const fetchEvidence = async (id: string) => {
    setEvidenceLoading(true);
    setStatus('Fetching evidence pack…');

    try {
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
      setStatus('Evidence pack ready.');
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Unable to fetch evidence';
      setStatus(message);
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsLoading(true);
    setStatus('Contacting Care-Plan Agent…');
    setPlanCard(null);
    setLabs(null);

    try {
      const response = await fetch('/api/care-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'dr_patel',
          patient_id: patientId,
          question,
        }),
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail || 'Care-Plan Agent error');
      }

      const data: PlanResponse = await response.json();
      setPlanCard(data.plan_card);
      setActiveTab('plan');
      setStatus('Plan card generated.');

      try {
        await fetchLabs(patientId);
      } catch (labError: unknown) {
        console.error(labError);
        const message = labError instanceof Error ? labError.message : 'Unable to load labs';
        setStatus((prev) => `${prev} ${message}`.trim());
      }
    } catch (err: unknown) {
      console.error(err);
      const message = err instanceof Error ? err.message : 'Something went wrong';
      setStatus(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main>
      <header>
        <h1>Care-Plan Assistant</h1>
        <p>
          Generate evidence-backed recommendations, preview nearby trials, and review labs for
          complex patients.
        </p>
      </header>

      <section className="card">
        <h2>Request a Plan</h2>
        <form onSubmit={handleSubmit}>
          <label htmlFor="patient-id">
            Patient ID
            <input
              id="patient-id"
              name="patient_id"
              value={patientId}
              onChange={(event) => setPatientId(event.target.value)}
              required
            />
          </label>

          <label htmlFor="question">
            Question for the agent
            <textarea
              id="question"
              name="question"
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              required
            />
          </label>

          <button type="submit" disabled={isLoading}>
            {isLoading ? 'Generating…' : 'Generate Plan Card'}
          </button>
        </form>
        {status ? <div className={`status${status.includes('error') ? ' error' : ''}`}>{status}</div> : null}
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
            onClick={() => fetchEvidence(patientId)}
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
