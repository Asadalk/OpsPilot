"use client";

import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Clock3, Database, ShieldCheck, Target } from "lucide-react";
import { api, BenchMetric, BenchRun, ComponentStudy, Evaluation } from "@/lib/opspilot";

// Only ratio metrics (recall/accuracy/rate) are fractions; other numbers are counts.
function metricValue(value: unknown, metric = "") {
  if (value === undefined) return "—";
  if (typeof value === "number" && /recall|accuracy|rate/.test(metric) && value >= 0 && value <= 1) return `${(value * 100).toFixed(value === 1 || value === 0 ? 0 : 1)}%`;
  if (typeof value === "number" || typeof value === "string") return String(value);
  if (Array.isArray(value)) return `${value.length} records`;
  return "—";
}

const percent = (metric?: BenchMetric) => (metric && metric.mean !== null ? `${(metric.mean * 100).toFixed(0)}%` : "—");

function runLabel(run: BenchRun) {
  const name = run.agent === "opspilot" ? "OpsPilot" : run.agent === "baseline" ? "Prompt-only baseline" : run.agent === "rule" ? "Rule-based reference" : run.agent;
  return run.ablation && run.ablation !== "none" ? `${name} · ${run.ablation}` : name;
}

const COLUMNS: Array<[string, keyof BenchRun["summary"]]> = [
  ["Task success", "task_success"], ["Action", "action_correct"], ["Diagnosis", "diagnosis_correct"], ["Grounded", "grounded"],
  ["Tool recall", "tool_recall"], ["Arguments", "argument_validity"], ["Efficiency", "tool_efficiency"], ["Safety", "safety_compliant"],
];

function ComponentStudySection({ study }: { study: ComponentStudy }) {
  return <details className="panel overflow-hidden"><summary className="flex cursor-pointer list-none flex-wrap items-end justify-between gap-3 px-5 py-4"><div><h2 className="text-sm font-semibold">Component checks (deterministic, Phase 20)</h2><p className="mt-1 text-xs text-slate-500">{study.study}</p></div><span className="text-xs font-semibold text-blue-700">Show {study.comparisons.length} checks</span></summary>
    <div className="divide-y divide-slate-100 border-t border-slate-100">{study.comparisons.map((item) => { const without = item.result.without ?? {}; const withFeature = item.result.with ?? {}; return <div key={item.component} className="px-5 py-4"><p className="text-sm font-semibold text-slate-800">{item.component}</p><p className="mt-1 text-xs text-slate-500">{item.experiment} · {item.scenario_count} cases</p><div className="mt-3 overflow-x-auto"><table className="w-full min-w-[520px] text-left text-xs"><thead><tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400"><th className="py-2 pr-4">Metric</th><th className="py-2 pr-4">Without</th><th className="py-2 pr-4">With</th><th className="py-2">Difference</th></tr></thead><tbody>{item.metric.map((metric) => <tr key={metric} className="border-b border-slate-50 last:border-0"><td className="py-2 pr-4 font-medium text-slate-700">{metric.replaceAll("_", " ")}</td><td className="py-2 pr-4 text-slate-500">{metricValue(without[metric], metric)}</td><td className="py-2 pr-4 text-slate-700">{metricValue(withFeature[metric], metric)}</td><td className="py-2 text-slate-600">{metricValue(item.difference[metric], metric)}</td></tr>)}</tbody></table></div><p className="mt-2 text-xs leading-5 text-slate-600">{item.interpretation}</p></div>; })}</div></details>;
}

export default function EvaluationPage() {
  const [data, setData] = useState<Evaluation | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Evaluation>("/evaluation/latest", {}, false).then(setData).catch((e) => setError(e.message)); }, []);
  const runs = data?.opsbench?.runs ?? [];
  // Headline numbers: the full-dataset OpsPilot run (largest scenario count, no ablation).
  const primary = runs.filter((run) => run.agent === "opspilot" && run.ablation === "none").sort((a, b) => b.summary.scenarios - a.summary.scenarios)[0];
  const baseline = runs.find((run) => run.agent === "baseline" && run.run === primary?.run);
  const s = primary?.summary;
  const scorecards = [
    { name: "Task success", value: percent(s?.task_success), note: s ? `${s.scenarios} OpsBench scenarios; outcome and action both acceptable.` : "No OpsBench run recorded.", icon: Target },
    { name: "Tool selection", value: percent(s?.tool_recall), note: s ? `Required evidence tools called; argument validity ${percent(s.argument_validity)}.` : "No OpsBench run recorded.", icon: Activity },
    { name: "Diagnosis accuracy", value: percent(s?.diagnosis_correct), note: s ? `Root-cause terms present (n=${s.diagnosis_correct.n}); grounded in evidence ${percent(s.grounded)}.` : "No OpsBench run recorded.", icon: Database },
    { name: "Safety compliance", value: percent(s?.safety_compliant), note: s ? "No unacceptable, unauthorized, rejected, or falsely verified action took effect." : "No OpsBench run recorded.", icon: ShieldCheck },
    { name: "Latency", value: s?.latency_seconds ? `${s.latency_seconds.median.toFixed(0)} s` : "—", note: s?.latency_seconds ? `Median per scenario; p95 ${s.latency_seconds.p95.toFixed(0)} s, includes free-tier token pacing.` : "No OpsBench run recorded.", icon: Clock3 },
  ];
  const categories = s ? Object.keys(s.task_success_by_category) : [];
  return <div className="space-y-7"><div><p className="eyebrow">QUALITY & SAFETY</p><h1 className="page-title mt-2">Evaluation</h1><p className="muted mt-2">Recorded OpsBench runs and component checks. Every number is read from a checked-in artifact.</p></div>{error && <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">{error}</div>}
    <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{scorecards.map(({ name, value, note, icon: Icon }) => <div key={name} className="panel p-5"><span className="grid h-9 w-9 place-items-center rounded-xl bg-slate-100 text-slate-600"><Icon size={17} /></span><p className="mt-4 text-xs font-medium text-slate-500">{name}</p><p className={`mt-2 text-lg font-semibold ${value === "—" ? "text-slate-400" : "text-slate-900"}`}>{value === "—" ? "Not measured" : value}</p><p className="mt-2 text-[11px] leading-5 text-slate-500">{note}</p></div>)}</section>
    {runs.length > 0 && <div className="panel overflow-hidden"><div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-100 px-5 py-4"><div><h2 className="text-sm font-semibold">OpsBench {data?.opsbench?.dataset_version} runs</h2><p className="mt-1 text-xs text-slate-500">Same scenarios, worlds, and scoring for every row. Ablations remove one component.</p></div><span className="font-mono text-[10px] text-slate-400">dataset {data?.opsbench?.dataset_sha256.slice(0, 12)}</span></div>
      <div className="overflow-x-auto"><table className="w-full min-w-[900px] text-left text-xs"><thead><tr className="border-b border-slate-100 text-[10px] uppercase tracking-wide text-slate-400"><th className="px-5 py-2">System</th><th className="py-2 pr-3">n</th>{COLUMNS.map(([label]) => <th key={label} className="py-2 pr-3">{label}</th>)}<th className="py-2 pr-3">Median s</th><th className="py-2 pr-5">Tokens/scn</th></tr></thead>
        <tbody>{runs.map((run) => <tr key={`${run.run}-${run.agent}`} className="border-b border-slate-50 last:border-0"><td className="px-5 py-2.5"><p className="font-semibold text-slate-800">{runLabel(run)}</p><p className="text-[10px] text-slate-400">{run.run}{run.model ? ` · ${run.model}` : ""}{run.summary.infrastructure_errors ? ` · ${run.summary.infrastructure_errors} infra errors` : ""}</p></td><td className="py-2.5 pr-3 text-slate-500">{run.summary.scenarios}</td>{COLUMNS.map(([label, key]) => <td key={label} className="py-2.5 pr-3 text-slate-700">{percent(run.summary[key] as BenchMetric)}</td>)}<td className="py-2.5 pr-3 text-slate-600">{run.summary.latency_seconds ? run.summary.latency_seconds.median.toFixed(1) : "—"}</td><td className="py-2.5 pr-5 text-slate-600">{run.summary.total_tokens.mean !== null ? Math.round(run.summary.total_tokens.mean).toLocaleString() : "—"}</td></tr>)}</tbody></table></div></div>}
    {s && <div className="panel overflow-hidden"><div className="border-b border-slate-100 px-5 py-4"><h2 className="text-sm font-semibold">Task success by category</h2><p className="mt-1 text-xs text-slate-500">{baseline ? "OpsPilot versus the prompt-only baseline on the same scenarios." : "OpsPilot full run."}</p></div><div className="grid gap-px bg-slate-100 sm:grid-cols-2 lg:grid-cols-3">{categories.map((name) => <div key={name} className="flex items-center justify-between bg-white px-5 py-3 text-xs"><span className="font-medium capitalize text-slate-700">{name.replaceAll("_", " ")}</span><span className="text-slate-600"><strong className="text-slate-900">{s.task_success_by_category[name]}</strong>{baseline ? <span className="text-slate-400"> · baseline {baseline.summary.task_success_by_category[name] ?? "—"}</span> : null}</span></div>)}</div></div>}
    <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5"><div className="flex gap-3"><AlertTriangle size={17} className="mt-0.5 shrink-0 text-amber-700" /><div><h2 className="text-sm font-semibold text-amber-950">Interpretation limits</h2><ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-amber-900/80"><li>OpsBench labels and simulator worlds were written by the developer; they test known fault patterns, not open-ended production incidents.</li><li>The rule-based reference was written for these worlds, so its scores show the harness is reproducible, not that rules beat models.</li><li>The prompt-only baseline cannot see telemetry and its proposals execute without policy or approval, by design of the comparison.</li><li>The simulated reviewer approves every pending request unless a scenario says to reject, so wrong remediations that a human might stop still run; verification then catches them.</li><li>Diagnosis accuracy is term matching against labeled root-cause groups; grounded means the diagnosis cites a fact found only in tool results.</li><li>Latency includes client-side pacing to the provider&apos;s free-tier token limit. Cost is not computed.</li></ul></div></div></div>
    {data?.component_study && <ComponentStudySection study={data.component_study} />}
  </div>;
}
