"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { LockKeyhole, ShieldCheck } from "lucide-react";
import { API_BASE_URL } from "@/lib/opspilot";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setBusy(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/token`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }) });
      if (!response.ok) throw new Error(response.status === 401 ? "Username or password is incorrect." : `Sign in failed (${response.status}).`);
      const result = await response.json() as { access_token: string };
      localStorage.setItem("opspilot.token", result.access_token);
      localStorage.setItem("opspilot.username", username);
      try {
        const payload = JSON.parse(atob(result.access_token.split(".")[1])) as { role?: string };
        localStorage.setItem("opspilot.role", payload.role ?? "viewer");
      } catch { localStorage.setItem("opspilot.role", "viewer"); }
      window.dispatchEvent(new Event("opspilot-session"));
      router.push(new URLSearchParams(window.location.search).get("next") ?? "/"); router.refresh();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to sign in."); }
    finally { setBusy(false); }
  }
  return <div className="mx-auto grid max-w-4xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-[0_18px_60px_rgba(15,23,42,.08)] md:grid-cols-[1fr_1fr]">
    <div className="flex min-h-[430px] flex-col justify-between bg-[#172b4d] p-8 text-white md:p-10"><div><span className="grid h-11 w-11 place-items-center rounded-2xl bg-white/10"><ShieldCheck /></span><p className="eyebrow mt-12 !text-blue-200">CONTROLLED OPERATIONS</p><h1 className="mt-3 text-3xl font-semibold tracking-tight">Investigate with clarity.<br />Act with control.</h1><p className="mt-4 max-w-sm text-sm leading-6 text-blue-100/80">Sign in to inspect agent runs, review approvals, and follow operational evidence.</p></div><p className="text-xs text-blue-200/70">OpsPilot simulator · actions affect simulated state only</p></div>
    <form onSubmit={submit} className="flex flex-col justify-center p-8 md:p-10"><span className="grid h-10 w-10 place-items-center rounded-xl bg-slate-100 text-slate-600"><LockKeyhole size={18} /></span><h2 className="mt-5 text-xl font-semibold text-slate-950">Welcome back</h2><p className="mt-1 text-sm text-slate-500">Use your OpsPilot account to continue.</p><label htmlFor="username" className="mt-7 text-xs font-semibold text-slate-700">Username</label><input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} className="mt-2 rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50" required /><label htmlFor="password" className="mt-4 text-xs font-semibold text-slate-700">Password</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} className="mt-2 rounded-xl border border-slate-200 px-3.5 py-3 text-sm outline-none focus:border-blue-500 focus:ring-4 focus:ring-blue-50" required />{error && <p role="alert" className="mt-3 text-xs text-rose-700">{error}</p>}<button disabled={busy} className="mt-6 rounded-xl bg-[#172b4d] px-4 py-3 text-sm font-semibold text-white hover:bg-[#223c63] disabled:opacity-50">{busy ? "Signing in…" : "Sign in"}</button><Link href="/" className="mt-4 text-center text-xs text-slate-500 hover:text-slate-900">Back to workspace</Link></form>
  </div>;
}
