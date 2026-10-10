"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Check, Database, ShieldCheck, Target } from "lucide-react";
import { api, Evaluation } from "@/lib/opspilot";

// Only ratio metrics (recall/accuracy/rate) are fractions; other numbers are counts.
function metricValue(value: unknown, metric = "") {
  if (value === undefined) return "—";
  if (typeof value === "number" && /recall|accuracy|rate/.test(metric) && value >= 0 && value <= 1) return `${(value * 100).toFixed(value === 1 || value === 0 ? 0 : 1)}%`;
  if (typeof value === "number" || typeof value === "string") return String(value);
  if (Array.isArray(value)) return `${value.length} records`;
  return "—";
}

export default function EvaluationPage() {
  const [study, setStudy] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Evaluation>("/evaluation/latest", {}, false).then(setStudy).catch((e) => setError(e.message)); }, []);
  const rag = study?.comparisons.find((item) => item.component === "RAG");
  const policy = study?.comparisons.find((item) => item.component === "Policy engine");
  const verification = study?.comparisons.find((item) => item.component === "Verification");
  const scorecards = [
    { name: "Task success", value: "Not measured", note: "No end-to-end task success scores in the saved study.", icon: Target },
    { name: "Tool selection accuracy", value: "Not measured", note: "Tool planning used a scripted read plan, not model-choice labels.", icon: Activity },
    { name: "Diagnosis accuracy", value: "Not measured", note: "Diagnosis quality was not scored in this component study.", icon: Database },
    { name: "Safety control checks", value: policy && typeof policy.result.with.denied_or_approval_gated === "number" && Array.isArray(policy.result.with.decisions) ? `${policy.result.with.denied_or_approval_gated} / ${policy.result.with.decisions.length} gated` : "Not measured", note: "Server policy denied or gated unsafe writes in the saved role/action decision set.", icon: ShieldCheck },
    { name: "Latency", value: "Not measured", note: "No comparable end-to-end latency dataset is recorded.", icon: Activity },
  ];
  return <div className="space-y-7"><div><p className="eyebrow">QUALITY & SAFETY</p><h1 className="page-title mt-2">Evaluation</h1><p className="muted mt-2">Recorded component checks and their limits. No unmeasured model scores are inferred.</p></div>{error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{error}</div>}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{scorecards.map(({ name, value, note, icon: Icon }) => <div key={name} className="panel p-5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-600"><Icon size={17} /></span><p className="mt-4 text-xs font-medium text-slate-500">{name}</p><p className={`mt-2 text-lg font-semibold ${value === "Not measured" ? "text-slate-400" : "text-slate-900"}`}>{value}</p><p className="mt-2 text-[11px] leading-5 text-slate-500">{note}</p></div>)}</section>
    {study && <><div className="panel overflow-hidden"><div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><h2 className="text-sm font-semibold">Saved ablation comparisons</h2><p className="mt-1 text-xs text-slate-500">{study.study}</p></div><span className="text-[10px] text-slate-400">Recorded {new Date(study.created_at).toLocaleString()} · {study.model_calls} model calls</span></div><div className="divide-y divide-slate-100">{study.comparisons.map((item) => { const without = item.result.without ?? {}; const withFeature = item.result.with ?? {}; return <details key={item.component} className="group px-5 py-4"><summary className="flex cursor-pointer list-none items-center justify-between gap-4"><div><p className="text-sm font-semibold text-slate-800">{item.component}</p><p className="mt-1 text-xs text-slate-500">{item.experiment} · {item.scenario_count} scenarios</p></div><span className="text-xs font-semibold text-blue-700">Inspect results</span></summary><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[580px] text-left text-xs"><thead><tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400"><th className="py-2 pr-4">Metric</th><th className="py-2 pr-4">Without</th><th className="py-2 pr-4">With</th><th className="py-2">Difference</th></tr></thead><tbody>{item.metric.map((metric) => <tr key={metric} className="border-b border-slate-50 last:border-0"><td className="py-2.5 pr-4 font-medium text-slate-700">{metric.replaceAll("_", " ")}</td><td className="py-2.5 pr-4 text-slate-500">{metricValue(without[metric], metric)}</td><td className="py-2.5 pr-4 text-slate-700">{metricValue(withFeature[metric], metric)}</td><td className="py-2.5 text-slate-600">{metricValue(item.difference[metric], metric)}</td></tr>)}</tbody></table></div><p className="mt-3 text-xs leading-5 text-slate-600">{item.interpretation}</p></details>; })}</div></div>
      <div className="grid gap-4 md:grid-cols-2">{rag && <div className="panel p-5"><div className="flex items-center gap-2"><Database size={16} className="text-blue-700" /><h3 className="text-sm font-semibold">Retrieval measurement</h3></div><p className="mt-3 text-sm text-slate-600">With hybrid RAG, source recall@3 was <strong>{metricValue(rag.result.with.source_recall_at_3, "source_recall_at_3")}</strong> and source accuracy@1 was <strong>{metricValue(rag.result.with.source_accuracy_at_1, "source_accuracy_at_1")}</strong> on {rag.scenario_count} labeled questions.</p></div>}{verification && <div className="panel p-5"><div className="flex items-center gap-2"><Check size={16} className="text-emerald-700" /><h3 className="text-sm font-semibold">Verification guard</h3></div><p className="mt-3 text-sm text-slate-600">Unverified resolution claims: <strong>{metricValue(verification.result.without.resolved_claims_without_success_verification)}</strong> in the naive comparator and <strong>{metricValue(verification.result.with.resolved_claims_without_success_verification)}</strong> with the verification guard. The with-feature result was {metricValue(verification.result.with.verification_status)}.</p></div>}</div>
      <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5"><div className="flex gap-3"><AlertTriangle size={17} className="mt-0.5 shrink-0 text-amber-700" /><div><h2 className="text-sm font-semibold text-amber-950">Interpretation limits</h2><ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-amber-900/80">{study.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul></div></div></div>
    </>}
  </div>;
}
