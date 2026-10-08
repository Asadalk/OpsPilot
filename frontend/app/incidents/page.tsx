"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, Search, Siren } from "lucide-react";
import { api, formatDate, Incident } from "@/lib/opspilot";

export default function IncidentsPage() {
  const [items, setItems] = useState<Incident[]>([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  useEffect(() => { api<Incident[]>("/incidents", {}, false).then(setItems).catch((e) => setError(e.message)); }, []);
  const filtered = items.filter((item) => filter === "all" || item.status === filter);
  return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">OPERATIONS</p><h1 className="page-title mt-2">Incidents</h1><p className="muted mt-2">Investigate incidents with service health, logs, metrics, and deployment evidence.</p></div><div className="flex rounded-xl border border-slate-200 bg-white p-1">{["all", "open", "investigating", "resolved"].map((status) => <button key={status} onClick={() => setFilter(status)} className={`rounded-lg px-3 py-2 text-xs font-medium capitalize ${filter === status ? "bg-slate-900 text-white" : "text-slate-500 hover:bg-slate-50"}`}>{status}</button>)}</div></div>
    {error && <p className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
    <div className="panel overflow-hidden"><div className="grid grid-cols-[1fr_150px_140px_150px_24px] gap-4 border-b border-slate-100 bg-slate-50/70 px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-slate-400"><span>Incident</span><span>Service</span><span>Severity</span><span>Status</span><span /></div><div className="divide-y divide-slate-100">{filtered.map((incident) => <Link key={incident.id} href={`/incidents/${incident.id}`} className="grid grid-cols-[1fr_150px_140px_150px_24px] items-center gap-4 px-5 py-4 transition hover:bg-slate-50"><div className="flex min-w-0 items-center gap-3"><span className={`grid h-9 w-9 shrink-0 place-items-center rounded-xl ${incident.status === "resolved" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}><Siren size={16} /></span><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{incident.title}</p><p className="mt-1 text-xs text-slate-400">INC-{String(incident.id).padStart(3, "0")} · {formatDate(incident.created_at)}</p></div></div><span className="text-xs text-slate-600">{incident.service}<span className="block pt-1 text-[10px] capitalize text-slate-400">{incident.environment}</span></span><span className={`w-fit rounded-md px-2 py-1 text-[10px] font-bold uppercase ${incident.severity === "sev1" ? "bg-rose-50 text-rose-700" : incident.severity === "sev2" ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-600"}`}>{incident.severity}</span><span className="text-xs capitalize text-slate-600">{incident.status}</span><ArrowUpRight size={15} className="text-slate-400" /></Link>)}{filtered.length === 0 && <div className="p-12 text-center"><Search className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-medium text-slate-600">No incidents in this view</p></div>}</div></div>
  </div>;
}
