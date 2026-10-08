"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Activity, ArrowLeft, BookOpen, CircleAlert, Clock3, FileText, Gauge, GitCommitHorizontal, LoaderCircle, ShieldAlert, Siren } from "lucide-react";
import { api, AgentRun, formatDate, Incident } from "@/lib/opspilot";

type Metric = { metric_name: string; value: number; timestamp: string };
type Log = { id: number; timestamp: string; level: string; message: string; trace_id: string };
type Deployment = { deployment_id: number; version: string; deployed_at: string; author: string; status: string };
type Investigation = { run_id: string; diagnosis: string | null; status: string; hypotheses: Array<{ hypothesis: string; score: number; supporting_evidence: Array<Record<string, unknown>>; contradicting_evidence: Array<Record<string, unknown>> }>; knowledge: Array<{ source: string; document: string; content: string }>; proposed_action: { action_type: string; target: string; reason: string } | null; approval: { id: number; decision: string } | null };

export default function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>();
  const [incident, setIncident] = useState<Incident | null>(null);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [investigation, setInvestigation] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Incident[]>("/incidents", {}, false).then(async (rows) => {
      const current = rows.find((row) => row.id === Number(incidentId));
      if (!current) throw new Error("Incident not found");
      setIncident(current);
      const [m, l, d] = await Promise.all([
        api<Metric[]>(`/services/${current.service_id}/metrics`, {}, false),
        api<Log[]>(`/services/${current.service_id}/logs`, {}, false),
        api<Deployment[]>(`/services/${current.service_id}/deployments`, {}, false),
      ]);
      setMetrics(m.slice(0, 6)); setLogs(l.slice(0, 6)); setDeployments(d.slice(0, 4));
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "Unable to load incident"));
    api<AgentRun[]>("/agent/runs?limit=100").then((data) => setRuns(data)).catch(() => undefined);
  }, [incidentId]);

  async function investigate() {
    if (!incident) return;
    setError(""); setBusy(true);
    try {
      const result = await api<Investigation>("/agent/investigate", { method: "POST", body: JSON.stringify({ request: `Investigate incident INC-${String(incident.id).padStart(3, "0")}: ${incident.title}. Service: ${incident.service}. Severity: ${incident.severity}. Current status: ${incident.status}. Review current metrics, logs, and recent deployments. Diagnose from evidence and propose a safe simulated action only if supported.` }) });
      setInvestigation(result);
      api<AgentRun[]>("/agent/runs?limit=100").then(setRuns).catch(() => undefined);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Investigation failed"); }
    finally { setBusy(false); }
  }
  const linkedRuns = incident ? runs.filter((run) => run.service === incident.service) : [];
  const newestRun = linkedRuns[0];
  const approvalId = investigation?.approval?.id ?? (newestRun?.events.find((event) => event.event_type === "approval" && typeof event.details.approval_id === "number")?.details.approval_id as number | undefined);
  const diagnosis = investigation?.diagnosis ?? newestRun?.diagnosis;
  const hypotheses = investigation?.hypotheses ?? newestRun?.hypotheses ?? [];
  const suggestedAction = investigation?.proposed_action ?? newestRun?.action_proposal ?? null;
  const verificationEvent = newestRun?.events.filter((event) => event.event_type === "verification").at(-1);

  return <div className="space-y-6">
    <Link href="/incidents" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-500 hover:text-slate-900"><ArrowLeft size={14} /> All incidents</Link>
    {incident ? <>
      <div className="panel p-6 md:p-7"><div className="flex flex-col justify-between gap-5 md:flex-row"><div><div className="flex items-center gap-2"><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-bold tracking-wide text-slate-600">INC-{String(incident.id).padStart(3, "0")}</span><span className={`rounded-md px-2 py-1 text-[10px] font-bold uppercase ${incident.severity === "sev1" ? "bg-rose-50 text-rose-700" : "bg-amber-50 text-amber-700"}`}>{incident.severity}</span><span className="text-xs capitalize text-slate-500">{incident.status}</span></div><h1 className="page-title mt-3">{incident.title}</h1><p className="mt-2 text-sm text-slate-500">{incident.service} · {incident.environment} · Opened {formatDate(incident.created_at)}</p></div><button onClick={investigate} disabled={busy || !incident || incident.status === "resolved"} className="inline-flex h-fit items-center justify-center gap-2 rounded-xl bg-[#172b4d] px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{busy ? <LoaderCircle size={16} className="animate-spin" /> : <Activity size={16} />}{busy ? "Investigating…" : "Start agent investigation"}</button></div>
        {error && <p role="alert" className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}{error.includes("token") || error.includes("credentials") ? <> · <Link className="font-semibold underline" href={`/login?next=/incidents/${incident.id}`}>Sign in</Link></> : null}</p>}
        {investigation && <div className="mt-5 flex flex-wrap items-center gap-3 rounded-xl border border-blue-100 bg-blue-50/60 p-4"><span className="text-xs font-semibold uppercase tracking-wide text-blue-800">Run {investigation.status}</span><Link href={`/runs/${investigation.run_id}`} className="text-xs font-semibold text-blue-800 underline">Open real event timeline</Link>{approvalId && <Link href={`/approvals/${approvalId}`} className="rounded-lg bg-amber-600 px-3 py-2 text-xs font-semibold text-white">Review pending approval</Link>}</div>}
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.25fr_.75fr]">
        <div className="space-y-5">
          <section className="panel"><div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4"><Gauge size={16} className="text-blue-700" /><h2 className="text-sm font-semibold">Service evidence</h2></div><div className="grid gap-4 p-5 sm:grid-cols-2"><div><h3 className="mb-3 text-xs font-semibold text-slate-700">Latest metrics</h3>{metrics.length ? <div className="space-y-2">{metrics.map((m, i) => <div key={`${m.metric_name}-${i}`} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs"><span className="text-slate-500">{m.metric_name.replaceAll("_", " ")}</span><strong>{m.value}</strong></div>)}</div> : <p className="text-xs text-slate-400">No metric samples available.</p>}</div><div><h3 className="mb-3 text-xs font-semibold text-slate-700">Recent deployments</h3>{deployments.length ? <div className="space-y-2">{deployments.map((d) => <div key={d.deployment_id} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2 text-xs"><span>{d.version} <span className="text-slate-400">· {d.author}</span></span><span className="capitalize text-slate-500">{d.status}</span></div>)}</div> : <p className="text-xs text-slate-400">No deployment records available.</p>}</div></div></section>
          <section className="panel"><div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4"><FileText size={16} className="text-rose-700" /><h2 className="text-sm font-semibold">Recent logs</h2></div><div className="divide-y divide-slate-100">{logs.map((log) => <div key={log.id} className="flex gap-3 px-5 py-3"><span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${log.level === "error" ? "bg-rose-500" : log.level === "warn" ? "bg-amber-400" : "bg-slate-300"}`} /><div><p className="text-xs leading-5 text-slate-700">{log.message}</p><p className="mt-1 text-[10px] text-slate-400">{formatDate(log.timestamp)} · {log.level} · {log.trace_id}</p></div></div>)}{logs.length === 0 && <p className="p-5 text-xs text-slate-400">No log events available.</p>}</div></section>
        </div>
        <div className="space-y-5">
          <section className="panel p-5"><div className="flex items-center gap-2"><CircleAlert size={16} className="text-amber-600" /><h2 className="text-sm font-semibold">Agent diagnosis</h2></div>{diagnosis ? <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-700">{diagnosis}</p> : <p className="mt-3 text-xs leading-5 text-slate-500">No diagnosis is recorded yet. Start an investigation to create a trace from real agent events.</p>}{newestRun && !investigation && <Link className="mt-3 inline-block text-xs font-semibold text-blue-700" href={`/runs/${newestRun.run_id}`}>Open latest service run →</Link>}</section>
          <section className="panel p-5"><div className="flex items-center gap-2"><ShieldAlert size={16} className="text-violet-700" /><h2 className="text-sm font-semibold">Hypotheses</h2></div><div className="mt-4 space-y-3">{hypotheses.map((hypothesis, i) => <div key={`${hypothesis.hypothesis}-${i}`} className="rounded-xl border border-slate-100 p-3"><div className="flex justify-between gap-3"><p className="text-xs font-medium text-slate-800">{hypothesis.hypothesis}</p><span className="text-xs font-semibold text-slate-500">{Math.round(hypothesis.score * 100)}%</span></div><div className="mt-2 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-blue-600" style={{ width: `${hypothesis.score * 100}%` }} /></div><p className="mt-2 text-[10px] text-slate-400">Model-assigned score, not calibrated probability</p></div>)}{hypotheses.length === 0 && <p className="text-xs text-slate-400">Hypotheses appear after an agent run.</p>}</div></section>
          <section className="panel p-5"><div className="flex items-center gap-2"><GitCommitHorizontal size={16} className="text-emerald-700" /><h2 className="text-sm font-semibold">Action & verification</h2></div>{suggestedAction ? <div className="mt-4 rounded-xl bg-slate-50 p-3"><p className="text-xs font-semibold text-slate-800">{suggestedAction.action_type} · {suggestedAction.target}</p><p className="mt-1 text-xs text-slate-500">{suggestedAction.reason}</p></div> : <p className="mt-3 text-xs text-slate-500">No action has been proposed.</p>}{approvalId && <Link href={`/approvals/${approvalId}`} className="mt-3 block rounded-lg bg-amber-50 px-3 py-2.5 text-xs font-semibold text-amber-800">Open approval record</Link>}{verificationEvent ? <div className="mt-3 rounded-lg border border-slate-100 p-3"><p className="text-xs font-semibold text-slate-800">Verification · {verificationEvent.status}</p><p className="mt-1 text-[10px] text-slate-500">{String(verificationEvent.details.reason ?? "Verification result recorded in the run trace.")}</p></div> : <p className="mt-3 text-xs text-slate-500">No verification event recorded yet.</p>}{investigation?.status === "paused" && !approvalId && <p className="mt-3 text-xs text-amber-700">Run paused for human approval. See the run trace for approval event details.</p>}{newestRun && <Link href={`/runs/${newestRun.run_id}`} className="mt-3 block text-xs font-semibold text-blue-700">View execution and verification events →</Link>}</section>
          <section className="panel p-5"><div className="flex items-center gap-2"><BookOpen size={16} className="text-slate-500" /><h2 className="text-sm font-semibold">Related run history</h2></div><div className="mt-3 space-y-2">{linkedRuns.slice(0, 3).map((run) => <Link key={run.run_id} href={`/runs/${run.run_id}`} className="block rounded-lg bg-slate-50 p-3"><p className="text-xs font-medium text-slate-700">{run.status} · {formatDate(run.started_at)}</p><p className="mt-1 truncate text-[10px] text-slate-500">{run.diagnosis ?? run.user_request}</p></Link>)}{linkedRuns.length === 0 && <p className="text-xs text-slate-400">No linked agent runs.</p>}</div></section>
        </div>
      </div>
    </> : <div className="panel p-10 text-sm text-slate-500">Loading incident record…</div>}
  </div>;
}
