"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowUpRight, Bell, Boxes, ClipboardCheck, Gauge, LogOut, ShieldCheck, Siren } from "lucide-react";
import { getSession } from "@/lib/opspilot";

const nav = [
  { href: "/", label: "Overview", icon: Gauge },
  { href: "/incidents", label: "Incidents", icon: Siren },
  { href: "/runs", label: "Agent runs", icon: Activity },
  { href: "/approvals", label: "Approvals", icon: ClipboardCheck },
  { href: "/evaluation", label: "Evaluation", icon: Boxes },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<{ username: string; role: string } | null>(null);
  useEffect(() => {
    const sync = () => setSession(getSession());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("opspilot-session", sync);
    return () => { window.removeEventListener("storage", sync); window.removeEventListener("opspilot-session", sync); };
  }, []);

  function signOut() {
    localStorage.removeItem("opspilot.token");
    localStorage.removeItem("opspilot.username");
    localStorage.removeItem("opspilot.role");
    setSession(null);
    window.dispatchEvent(new Event("opspilot-session"));
  }

  return (
    <div className="min-h-screen bg-[#f5f7fa]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[248px] flex-col border-r border-slate-200 bg-white lg:flex">
        <Link href="/" className="flex h-[76px] items-center gap-3 border-b border-slate-100 px-6">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#172b4d] text-white"><ShieldCheck size={19} /></span>
          <span><strong className="block text-[15px] tracking-tight text-slate-900">OpsPilot</strong><small className="text-[11px] text-slate-500">Operations workspace</small></span>
        </Link>
        <div className="px-4 pt-7">
          <p className="eyebrow px-3 pb-2">WORKSPACE</p>
          <nav className="space-y-1">
            {nav.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className="nav-link"><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{label === "Approvals" && <Bell className="ml-auto text-slate-400" size={14} />}</Link>)}
          </nav>
        </div>
        <div className="mt-auto border-t border-slate-100 p-4">
          <Link href="/tasks/new" className="nav-link text-slate-500"><ArrowUpRight size={16} /><span>Task extraction</span></Link>
          <div className="mt-4 flex items-center gap-3 rounded-xl bg-slate-50 p-3">
            <div className="grid h-8 w-8 place-items-center rounded-full bg-[#dce7f5] text-xs font-bold uppercase text-[#24466e]">{session?.username.slice(0, 1) ?? "?"}</div>
            <div className="min-w-0 flex-1"><p className="truncate text-xs font-semibold text-slate-800">{session?.username ?? "Not signed in"}</p><p className="text-[11px] capitalize text-slate-500">{session?.role ?? "Read access"}</p></div>
            {session ? <button aria-label="Sign out" title="Sign out" onClick={signOut} className="text-slate-400 hover:text-slate-700"><LogOut size={15} /></button> : <Link className="text-xs font-semibold text-blue-700" href="/login">Sign in</Link>}
          </div>
        </div>
      </aside>
      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b border-slate-200 bg-white/95 px-5 backdrop-blur md:px-9">
          <div className="flex items-center gap-2 lg:hidden"><ShieldCheck size={20} /><span className="font-semibold">OpsPilot</span></div>
          <nav className="flex gap-1 overflow-x-auto lg:hidden">{nav.map((item) => <Link key={item.href} className="rounded-lg px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100" href={item.href}>{item.label}</Link>)}</nav>
          <div className="hidden items-center gap-2 text-xs text-slate-500 lg:flex"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Simulator environment</div>
          {session ? <span className="hidden rounded-full border border-slate-200 px-3 py-1.5 text-xs font-medium capitalize text-slate-600 sm:inline-flex">{session.role} access</span> : <Link href="/login" className="rounded-lg bg-[#172b4d] px-3.5 py-2 text-xs font-semibold text-white">Sign in</Link>}
        </header>
        <main className="mx-auto max-w-[1440px] px-5 py-7 md:px-9 md:py-9">{children}</main>
      </div>
    </div>
  );
}
