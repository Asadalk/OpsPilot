"use client";

import { useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type Approval = {
  id: number;
  requested_at: string;
  expires_at: string;
  proposal: { action_type: string; target: string; reason: string; risk_level: string };
};

export default function ApprovalsPage() {
  const [token, setToken] = useState("");
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [message, setMessage] = useState("");

  async function load() {
    setMessage("");
    try {
      const response = await fetch(`${API_BASE_URL}/approvals`, {
        headers: { Authorization: `Bearer ${token}` }, cache: "no-store",
      });
      if (!response.ok) throw new Error(`Unable to load pending approvals (${response.status})`);
      setApprovals((await response.json()) as Approval[]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to load pending approvals");
    }
  }

  return (
    <section className="mx-auto max-w-3xl rounded-xl border border-slate-200 bg-white p-6 shadow-soft">
      <h1 className="text-2xl font-semibold text-slate-900">Pending approvals</h1>
      <p className="mt-2 text-sm text-slate-600">Sign in with an operator or admin token to review and decide on simulated actions.</p>
      <div className="mt-5 flex gap-3">
        <input aria-label="Bearer token" value={token} onChange={(event) => setToken(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-300 p-3 text-sm" placeholder="Paste a JWT" />
        <button type="button" onClick={load} disabled={!token} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50">Load</button>
      </div>
      {message && <p role="status" className="mt-4 text-sm text-rose-700">{message}</p>}
      <ul className="mt-5 space-y-3">
        {approvals.map((approval) => (
          <li key={approval.id} className="rounded-lg border border-slate-200 p-4">
            <p className="font-medium text-slate-900">{approval.proposal.action_type} · {approval.proposal.target}</p>
            <p className="mt-1 text-sm text-slate-600">{approval.proposal.reason}</p>
            <p className="mt-1 text-xs text-slate-500">{approval.proposal.risk_level} risk · expires {new Date(approval.expires_at).toLocaleString()}</p>
            <a className="mt-3 inline-block text-sm font-medium text-blue-700 underline" href={`/approvals/${approval.id}`}>Review request</a>
          </li>
        ))}
      </ul>
      {!message && approvals.length === 0 && <p className="mt-5 text-sm text-slate-600">No pending approvals loaded.</p>}
    </section>
  );
}
