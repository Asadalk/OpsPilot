"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Approval = {
  id: number;
  decision: "pending" | "approved" | "rejected" | "expired";
  requested_at: string;
  expires_at: string;
  decided_by: string | null;
  reason: string | null;
  proposal: {
    action_type: string;
    target: string;
    reason: string;
    risk_level: string;
    status: string;
    evidence: Array<Record<string, unknown>>;
  };
  execution_result: Record<string, unknown> | null;
};

type ActionVerification = {
  status: "SUCCESS" | "FAILED" | "INCONCLUSIVE";
  reason: string;
  attempt_count: number;
  max_automatic_attempts: number;
  escalated: boolean;
  attempts: Array<{
    attempt: number;
    before: { state: string; metrics: Record<string, number> };
    after: { state: string; metrics: Record<string, number> };
    verification: string;
    reason: string;
    reinvestigation?: { state: string; metrics: Record<string, number> };
  }>;
};

function metricsSummary(metrics: Record<string, number>) {
  const entries = Object.entries(metrics);
  if (!entries.length) return "No metric samples";
  return entries.map(([name, value]) => `${name}: ${value}`).join(" · ");
}

export default function ApprovalPage() {
  const params = useParams<{ approvalId: string }>();
  const [token, setToken] = useState("");
  const [approval, setApproval] = useState<Approval | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("Enter an approval token to load this request.");
  const [loading, setLoading] = useState(false);

  async function loadApproval() {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/approvals/${params.approvalId}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Unable to load approval (${response.status})`);
      setApproval((await response.json()) as Approval);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load approval");
    } finally {
      setLoading(false);
    }
  }

  async function decide(decision: "approve" | "reject") {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/approvals/${params.approvalId}/${decision}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason }),
      });
      if (!response.ok) throw new Error(`Decision failed (${response.status})`);
      setApproval((await response.json()) as Approval);
      setMessage(decision === "approve" ? "Approval recorded and simulated action resumed." : "Rejection recorded; action was not executed.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Decision failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-2xl">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-soft">
        <h1 className="text-2xl font-semibold text-slate-900">Human approval</h1>
        <p className="mt-2 text-sm text-slate-600">Review the proposed action before it can resume.</p>
        <label className="mt-6 block text-sm font-medium text-slate-700" htmlFor="token">Bearer token</label>
        <input id="token" value={token} onChange={(event) => setToken(event.target.value)} className="mt-2 w-full rounded-lg border border-slate-300 p-3 text-sm" placeholder="Paste a JWT" />
        <button type="button" onClick={loadApproval} disabled={loading || !token} className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Load approval</button>
        {approval && (
          <div className="mt-6 space-y-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-700">
            <p><strong>Action:</strong> {approval.proposal.action_type}</p>
            <p><strong>Target:</strong> {approval.proposal.target}</p>
            <p><strong>Risk:</strong> {approval.proposal.risk_level}</p>
            <p><strong>Status:</strong> {approval.decision}</p>
            <p><strong>Reason:</strong> {approval.proposal.reason}</p>
            {approval.decision === "pending" && (
              <>
                <label className="block pt-3 text-sm font-medium" htmlFor="decision-reason">Decision reason</label>
                <textarea id="decision-reason" value={reason} onChange={(event) => setReason(event.target.value)} className="min-h-24 w-full rounded-lg border border-slate-300 p-3" />
                <div className="flex gap-3 pt-2">
                  <button type="button" onClick={() => decide("approve")} disabled={loading} className="rounded-lg bg-emerald-700 px-4 py-2 font-medium text-white disabled:opacity-50">Approve</button>
                  <button type="button" onClick={() => decide("reject")} disabled={loading} className="rounded-lg bg-rose-700 px-4 py-2 font-medium text-white disabled:opacity-50">Reject</button>
                </div>
              </>
            )}
            {approval.execution_result && (() => {
              const result = approval.execution_result as { verification?: ActionVerification; resolved_incident_ids?: number[] };
              const verification = result.verification;
              if (!verification) return null;
              return (
                <div className="mt-4 border-t border-slate-200 pt-4">
                  <h2 className="font-semibold text-slate-900">Execution verification: {verification.status}</h2>
                  <p className="mt-1">{verification.reason}</p>
                  <p className="mt-1 text-xs text-slate-500">Attempts: {verification.attempt_count} / {verification.max_automatic_attempts}{verification.escalated ? " · Escalation required" : ""}</p>
                  {verification.attempts.map((attempt) => (
                    <div key={attempt.attempt} className="mt-3 rounded border border-slate-200 bg-white p-3">
                      <p className="font-medium">Attempt {attempt.attempt}: {attempt.verification}</p>
                      <p className="mt-1">Before · {attempt.before.state} · {metricsSummary(attempt.before.metrics)}</p>
                      <p className="mt-1">After · {attempt.after.state} · {metricsSummary(attempt.after.metrics)}</p>
                      {attempt.reinvestigation && <p className="mt-1">Reinvestigation · {attempt.reinvestigation.state} · {metricsSummary(attempt.reinvestigation.metrics)}</p>}
                    </div>
                  ))}
                  {(result.resolved_incident_ids ?? []).length > 0 && <p className="mt-3 font-medium text-emerald-800">Resolved incident IDs: {result.resolved_incident_ids?.join(", ")}</p>}
                </div>
              );
            })()}
          </div>
        )}
        {message && <p className="mt-4 text-sm text-slate-600">{message}</p>}
      </div>
    </section>
  );
}
