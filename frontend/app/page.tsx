"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowDownRight, ArrowUpRight, Clock3, ShieldAlert, Siren, CircleCheck } from "lucide-react";
import { AgentRun, api, durationLabel, formatDate, Incident } from "@/lib/opspilot";

function Metric({ label, value, hint, icon: Icon, tone = "navy" }: { label: string; value: string | number; hint: string; icon: typeof Siren; tone?: string }) {
  const tones: Record<string, string> = { navy: "bg-[#e9eff8] text-[#345a87]", amber: "bg-amber-50 text-amber-700", green: "bg-emerald-50 text-emerald-700", violet: "bg-violet-50 text-violet-700" };
  return <div className="panel p-5"><div className="flex items-start justify-between"><div><p className="text-xs font-medium text-slate-500">{label}</p><p className="mt-3 text-[30px] font-semibold leading-none tracking-tight text-slate-950">{value}</p></div><span className={`grid h-10 w-10 place-items-center rounded-xl ${tones[tone]}`}><Icon size={18} /></span></div><p className="mt-4 text-xs text-slate-500">{hint}</p></div>;
}

export default function DashboardPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [approvals, setApprovals] = useState<Array<{ id: number }>>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    Promise.allSettled([api<Incident[]>("/incidents", {}, false), api<AgentRun[]>("/agent/runs?limit=100"), api<Array<{ id: number }>>("/approvals")])
      .then(([incidentResult, runResult, approvalResult]) => {
        if (incidentResult.status === "fulfilled") setIncidents(incidentResult.value);
        if (runResult.status === "fulfilled") setRuns(runResult.value);
        if (approvalResult.status === "fulfilled") setApprovals(approvalResult.value);
        const rejected = [incidentResult, runResult, approvalResult].find((result) => result.status === "rejected");
        if (rejected?.status === "rejected") setError(rejected.reason instanceof Error ? rejected.reason.message : "Sign in to load protected records");
      })
      .finally(() => setLoaded(true));
  }, []);
  const active = incidents.filter((item) => item.status !== "resolved");
  const resolved = incidents.filter((item) => item.status === "resolved");
  const finalized = runs.filter((run) => run.status === "completed" || run.status === "failed");
  const successRate = finalized.length ? `${Math.round(finalized.filter((run) => run.status === "completed").length / finalized.length * 100)}%` : "—";
  const durations = finalized.filter((run) => run.completed_at).map((run) => new Date(run.completed_at!).getTime() - new Date(run.started_at).getTime()).filter((n) => n >= 0);
  const averageDuration = durations.length ? durationLabel(Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)) : "—";
  return <div className="space-y-8">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><p className="eyebrow">OPERATIONS OVERVIEW</p><h1 className="page-title mt-2">Good day. Here’s your operations picture.</h1><p className="muted mt-2">Live incident, agent, and approval data from the OpsPilot simulator.</p></div><Link href="/incidents" className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#172b4d] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#223c63]"><Siren size={16} /> Review incidents</Link></div>
    {error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{error}. Sign in with a valid OpsPilot account to load agent and approval records.</div>}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      <Metric label="Active incidents" value={loaded ? active.length : "—"} hint={`${active.filter((i) => i.severity === "sev1" || i.severity === "sev2").length} severity 1–2`} icon={Siren} tone="amber" />
      <Metric label="Resolved incidents" value={loaded ? resolved.length : "—"} hint="From incident records" icon={CircleCheck} tone="green" />
      <Metric label="Agent success rate" value={loaded ? successRate : "—"} hint={`${finalized.length} terminal runs · completed ÷ completed + failed`} icon={Activity} tone="navy" />
      <Metric label="Pending approvals" value={loaded ? approvals.length : "—"} hint="Waiting for an authorized reviewer" icon={ShieldAlert} tone="violet" />
      <Metric label="Average run duration" value={loaded ? averageDuration : "—"} hint={`${durations.length} runs with recorded completion`} icon={Clock3} tone="navy" />
    </section>
    <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
      <section className="panel overflow-hidden"><div className="flex items-center justify-between border-b border-slate-100 px-5 py-4"><div><h2 className="text-sm font-semibold text-slate-900">Incident queue</h2><p className="mt-1 text-xs text-slate-500">Current simulator incidents</p></div><Link href="/incidents" className="text-xs font-semibold text-blue-700">All incidents <ArrowUpRight className="ml-1 inline" size={13} /></Link></div>
        <div className="divide-y divide-slate-100">{incidents.slice(0, 6).map((incident) => <Link key={incident.id} href={`/incidents/${incident.id}`} className="flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50"><span className={`h-2 w-2 shrink-0 rounded-full ${incident.status === "resolved" ? "bg-emerald-500" : incident.severity === "sev1" ? "bg-rose-500" : "bg-amber-400"}`} /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-slate-900">{incident.title}</p><p className="mt-1 text-xs text-slate-500">{incident.service} · {incident.environment} · {formatDate(incident.updated_at)}</p></div><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-600">{incident.severity}</span><span className="hidden w-24 text-right text-xs capitalize text-slate-500 sm:block">{incident.status}</span></Link>)}{loaded && incidents.length === 0 && <p className="px-5 py-10 text-center text-sm text-slate-500">No incidents are recorded.</p>}</div>
      </section>
      <section className="panel"><div className="border-b border-slate-100 px-5 py-4"><h2 className="text-sm font-semibold text-slate-900">Recent agent activity</h2><p className="mt-1 text-xs text-slate-500">Runs reconstructed from stored events</p></div><div className="divide-y divide-slate-100">{runs.slice(0, 5).map((run) => <Link key={run.run_id} href={`/runs/${run.run_id}`} className="block px-5 py-4 hover:bg-slate-50"><div className="flex items-center justify-between gap-3"><span className="truncate text-xs font-semibold text-slate-800">{run.service ?? run.user_request}</span><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${run.status === "completed" ? "bg-emerald-50 text-emerald-700" : run.status === "paused" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"}`}>{run.status}</span></div><p className="mt-2 line-clamp-1 text-xs text-slate-500">{run.diagnosis ?? "Investigation in progress"}</p><p className="mt-2 text-[10px] text-slate-400">{formatDate(run.started_at)} · {run.events.length} events</p></Link>)}{loaded && runs.length === 0 && <div className="px-5 py-8 text-center"><p className="text-sm text-slate-500">No agent runs found.</p><p className="mt-1 text-xs text-slate-400">Open an incident to start an investigation.</p></div>}</div><Link href="/runs" className="block border-t border-slate-100 px-5 py-3 text-xs font-semibold text-blue-700">View all runs <ArrowUpRight className="ml-1 inline" size={13} /></Link></section>
    </div>
    <div className="flex items-center gap-2 text-xs text-slate-400"><ArrowDownRight size={14} /> Metrics are calculated from stored simulator records and agent run timestamps.</div>
  </div>;
}
