"use client";
import { useEffect, useState } from "react";
import { ReportView, type CaseState } from "./report";

const TERMINAL = new Set(["completed", "failed", "cancelled", "incomplete"]);

export default function Page() {
  const [caseId, setCaseId] = useState<string>();
  const [state, setState] = useState<CaseState>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);

  // Reopen a case from the URL (?case=...), so a refresh does not lose it.
  useEffect(() => setCaseId(new URLSearchParams(location.search).get("case") ?? undefined), []);

  useEffect(() => {
    if (!caseId) return;
    let stop = false;
    const poll = async () => {
      const res = await fetch(`/api/cases/${caseId}`);
      const body = (await res.json()) as CaseState & { error?: string };
      if (stop) return;
      if (!res.ok) return setError(body.error ?? `HTTP ${res.status}`);
      setState(body);
      if (!TERMINAL.has(body.status)) setTimeout(poll, 4000);
    };
    void poll();
    return () => {
      stop = true;
    };
  }, [caseId]);

  async function upload(file: File) {
    setBusy(true);
    setError(undefined);
    setState(undefined);
    const form = new FormData();
    form.set("file", file);
    const res = await fetch("/api/cases", { method: "POST", body: form });
    const body = (await res.json().catch(() => ({}))) as { caseId?: string; error?: string };
    setBusy(false);
    if (!res.ok || !body.caseId) return setError(body.error ?? `Upload failed (HTTP ${res.status}).`);
    history.replaceState(null, "", `?case=${body.caseId}`);
    setCaseId(body.caseId);
  }

  return (
    <>
      <header>
        <strong>Medical underwriting copilot</strong>
        <p>Drafts a report for a human underwriter. It does not decide. Sample data is synthetic.</p>
      </header>
      <main>
        <label>
          Medical record (PDF):{" "}
          <input
            type="file"
            accept="application/pdf"
            disabled={busy}
            onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])}
          />
        </label>
        {busy && <p>Reading the record with OCR…</p>}
        {error && <p role="alert">{error}</p>}
        {state && !TERMINAL.has(state.status) && (
          <div data-testid="progress">
            <p>Drafting and reviewing the report ({state.status}). This takes a few minutes.</p>
            <ul className="steps">
              {state.steps.map((s, i) => (
                <li key={i}>{s.name}</li>
              ))}
            </ul>
          </div>
        )}
        {state && state.status !== "completed" && TERMINAL.has(state.status) && (
          <p role="alert">The run ended with status {state.status}. {state.error}</p>
        )}
        {state?.status === "completed" && caseId && <ReportView caseId={caseId} state={state} />}
      </main>
    </>
  );
}
