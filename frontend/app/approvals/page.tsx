"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowUpRight, ClipboardCheck, ShieldAlert } from "lucide-react";
import { api, Approval, formatDate } from "@/lib/opspilot";

export default function ApprovalsPage() {
  const [items, setItems] = useState<Approval[]>([]);
  const [tab, setTab] = useState("pending");
  const [error, setError] = useState("");
  useEffect(() => { api<Approval[]>("/approvals?decision=all").then(setItems).catch((e) => setError(e.message)); }, []);
  const visible = items.filter((approval) => tab === "all" || approval.decision === tab);
  return <div className="space-y-6"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="eyebrow">HUMAN CONTROL</p><h1 className="page-title mt-2">Approvals</h1><p className="muted mt-2">Review the action details and recorded execution outcome.</p></div><div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500"><ShieldAlert size={15} className="text-amber-600" /> Actions remain paused until an authorized decision</div></div>
    {error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{error} · <Link href="/login?next=/approvals" className="font-semibold underline">Sign in with operator or admin access</Link></div>}
    <div className="flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-white p-1.5">{["pending", "approved", "rejected", "expired", "all"].map((status) => { const count = status === "all" ? items.length : items.filter((item) => item.decision === status).length; return <button key={status} onClick={() => setTab(status)} className={`rounded-lg px-3.5 py-2 text-xs font-medium capitalize ${tab === status ? "bg-[#172b4d] text-white" : "text-slate-500 hover:bg-slate-50"}`}>{status}<span className={`ml-2 text-[10px] ${tab === status ? "text-blue-200" : "text-slate-400"}`}>{count}</span></button>; })}</div>
    <div className="grid gap-4 lg:grid-cols-2">{visible.map((item) => <Link key={item.id} href={`/approvals/${item.id}`} className="panel block p-5 transition hover:-translate-y-0.5 hover:shadow-md"><div className="flex items-start justify-between gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-amber-50 text-amber-700"><ClipboardCheck size={18} /></span><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${item.decision === "pending" ? "bg-amber-50 text-amber-700" : item.decision === "approved" ? "bg-emerald-50 text-emerald-700" : item.decision === "rejected" ? "bg-rose-50 text-rose-700" : "bg-slate-100 text-slate-500"}`}>{item.decision}</span></div><h2 className="mt-4 text-base font-semibold text-slate-900">{item.proposal.action_type.replaceAll("_", " ")}</h2><p className="mt-1 text-sm text-slate-600">Target: <span className="font-medium text-slate-800">{item.proposal.target}</span></p><p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-500">{item.proposal.reason}</p><div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4"><span className="text-[10px] text-slate-400">Requested {formatDate(item.requested_at)} · run {item.run_id.slice(0, 8)}</span><span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700">View record <ArrowUpRight size={13} /></span></div></Link>)}{visible.length === 0 && !error && <div className="panel col-span-full py-14 text-center"><ClipboardCheck size={24} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-medium text-slate-700">No {tab} approval records</p><p className="mt-1 text-xs text-slate-400">Approval history is read directly from the backend.</p></div>}</div>
  </div>;
}
