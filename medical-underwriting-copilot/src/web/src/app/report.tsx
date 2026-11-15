"use client";
import { useState } from "react";

type Evidence = { fact: string; page: number };
type Condition = {
  name: string;
  icd10: string;
  status: string;
  first_documented: string;
  evidence: Evidence[];
  guideline_refs: string[];
};
type Visit = { date: string; setting: string; reason: string; findings: string; page: number };
type Lab = { test: string; value: string; unit: string; date: string; interpretation: string; page: number };
type Report = {
  summary: string;
  conditions: Condition[];
  visits: Visit[];
  labs: Lab[];
  discrepancies: string[];
  ocr_attention: string[];
  recommendation: { decision: string; rationale: string; guideline_refs: string[] };
};
type Review = { passed: boolean; summary: string; issues: { severity: string; detail: string }[] };
type Flag = { text: string; confidence: number; page: number };

export type CaseState = {
  status: string;
  steps: { type: string; name: string }[];
  error?: string;
  filename?: string;
  record?: string;
  lowConfidence?: Flag[];
  report?: Report;
  review?: Review;
  revisions?: number;
};

export function ReportView({ caseId, state }: { caseId: string; state: CaseState }) {
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState<"report" | "source">("report");
  const { report, review } = state;
  const Cite = ({ p }: { p: number }) => (
    <button className="cite" onClick={() => setPage(p)} title="Show this page">
      p.{p}
    </button>
  );

  return (
    <div className="split">
      {/* Remount on page change: browsers' PDF viewers read #page only when the frame loads. */}
      <iframe key={page} title="Original record" src={`/api/cases/${caseId}/document#page=${page}`} />
      <div className="panel">
        <div className="tabs">
          <button onClick={() => setTab("report")}>Report</button>
          <button onClick={() => setTab("source")}>OCR source ({state.lowConfidence?.length ?? 0} flags)</button>
        </div>
        {tab === "source" && <Source record={state.record ?? ""} flags={state.lowConfidence ?? []} onPage={setPage} />}
        {tab === "report" && !report && <p role="alert">{state.error ?? "No report was submitted."}</p>}
        {tab === "report" && report && (
          <div data-testid="report">
            {review && (
              <section>
                <span className={`badge ${review.passed ? "pass" : "fail"}`}>
                  Second-model review: {review.passed ? "passed" : "not passed"}
                </span>{" "}
                <small>
                  {review.summary} Revisions: {state.revisions ?? 0}.
                </small>
                {!review.passed && (
                  <ul>
                    {review.issues.map((i, n) => (
                      <li key={n}>
                        <b>{i.severity}</b>: {i.detail}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            )}
            <section>
              <h2>Recommendation: {report.recommendation.decision}</h2>
              <p>{report.recommendation.rationale}</p>
              <small>Guidelines: {report.recommendation.guideline_refs.join("; ")}</small>
            </section>
            <section>
              <h2>Summary</h2>
              <p>{report.summary}</p>
            </section>
            <section>
              <h2>Conditions</h2>
              <table>
                <tbody>
                  {report.conditions.map((c, n) => (
                    <tr key={n}>
                      <td>
                        <b>{c.name}</b>
                        <br />
                        {c.icd10} · {c.status} · since {c.first_documented}
                      </td>
                      <td>
                        {c.evidence.map((e, k) => (
                          <div key={k}>
                            {e.fact} <Cite p={e.page} />
                          </div>
                        ))}
                      </td>
                      <td>{c.guideline_refs.join("; ")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section>
              <h2>Visits</h2>
              <table>
                <tbody>
                  {report.visits.map((v, n) => (
                    <tr key={n}>
                      <td>{v.date}</td>
                      <td>
                        {v.setting}: {v.reason}
                      </td>
                      <td>
                        {v.findings} <Cite p={v.page} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section>
              <h2>Laboratory results</h2>
              <table>
                <tbody>
                  {report.labs.map((l, n) => (
                    <tr key={n}>
                      <td>{l.date}</td>
                      <td>{l.test}</td>
                      <td>
                        {l.value} {l.unit}
                      </td>
                      <td>
                        {l.interpretation} <Cite p={l.page} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            {[
              ["Discrepancies", report.discrepancies],
              ["OCR values to confirm", report.ocr_attention],
            ].map(([title, items]) => (
              <section key={title as string}>
                <h2>{title as string}</h2>
                {(items as string[]).length ? (
                  <ul>
                    {(items as string[]).map((t, n) => (
                      <li key={n}>{t}</li>
                    ))}
                  </ul>
                ) : (
                  <p>None.</p>
                )}
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Source({ record, flags, onPage }: { record: string; flags: Flag[]; onPage: (p: number) => void }) {
  return (
    <div data-testid="source">
      {flags.length > 0 && (
        <section>
          <h2>Low-confidence numbers</h2>
          <ul>
            {flags.map((f, n) => (
              <li key={n}>
                <span className="flag">{f.text}</span> ({f.confidence}){" "}
                <button className="cite" onClick={() => onPage(f.page)}>
                  p.{f.page}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <pre>{record}</pre>
    </div>
  );
}
