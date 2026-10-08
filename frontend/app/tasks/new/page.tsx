"use client";

import { ChangeEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { extractTasks } from "@/lib/api";

export default function ExtractTasksPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function handleExtract() {
    setError(null);
    if (!text.trim()) { setError("Please paste some notes first."); return; }
    setLoading(true);
    try { await extractTasks({ text }); router.push("/board"); }
    catch (reason: unknown) { setError(reason instanceof Error ? reason.message : "Failed to extract tasks."); }
    finally { setLoading(false); }
  }
  return <div className="mx-auto max-w-3xl space-y-5"><Link href="/board" className="text-xs font-semibold text-slate-500">← Task board</Link><section className="panel p-6 md:p-8"><p className="eyebrow">LEGACY WORKFLOW</p><h1 className="page-title mt-2">Extract tasks from notes</h1><p className="muted mt-2">Turn meeting notes, emails, or a task list into structured work items.</p><label htmlFor="notes" className="mt-7 block text-xs font-semibold text-slate-700">Input text</label><textarea id="notes" value={text} onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setText(event.target.value)} placeholder="Paste your meeting notes, emails, or task list…" className="mt-2 min-h-[250px] w-full rounded-xl border border-slate-200 bg-white p-4 text-sm leading-6 text-slate-900 outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50" /><div className="mt-4 flex items-center gap-4"><button type="button" onClick={handleExtract} disabled={loading} className="rounded-xl bg-[#172b4d] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#223c63] disabled:opacity-50">{loading ? "Extracting…" : "Extract tasks"}</button>{loading && <span className="text-xs text-slate-500">Processing notes with AI…</span>}</div>{error && <p role="alert" className="mt-4 text-sm text-rose-700">{error}</p>}</section></div>;
}
