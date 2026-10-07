"use client";

import { ChangeEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { extractTasks } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleExtract() {
    setError(null);

    if (!text.trim()) {
      setError("Please paste some notes first.");
      return;
    }

    setLoading(true);
    try {
      await extractTasks({ text });
      router.push("/board");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to extract tasks.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="mx-auto max-w-4xl">
      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-soft">
        <h1 className="text-2xl font-semibold text-slate-900">AI Internal Ops Pilot</h1>
        <p className="mt-2 text-sm text-slate-600">
          Paste your meeting notes, emails, or task list and automatically turn them into structured work items.
        </p>

        <label htmlFor="notes" className="mt-6 block text-sm font-medium text-slate-700">
          Input Text
        </label>
        <textarea
          id="notes"
          value={text}
          onChange={(event: ChangeEvent<HTMLTextAreaElement>) => setText(event.target.value)}
          placeholder="Paste your meeting notes, emails, or task list..."
          className="mt-2 min-h-[260px] w-full rounded-lg border border-slate-300 bg-white p-4 text-sm text-slate-900 outline-none focus:border-slate-500"
        />

        <div className="mt-5 flex items-center gap-4">
          <button
            type="button"
            onClick={handleExtract}
            disabled={loading}
            className="inline-flex items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-500"
          >
            Extract Tasks
          </button>

          {loading ? (
            <div className="inline-flex items-center gap-2 text-sm text-slate-600">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-900" />
              Extracting tasks with AI...
            </div>
          ) : null}
        </div>

        {error ? <p className="mt-4 text-sm font-medium text-red-600">{error}</p> : null}
      </div>
    </section>
  );
}
