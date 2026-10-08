export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export type Incident = {
  id: number;
  title: string;
  severity: string;
  status: string;
  service_id: number;
  service: string;
  environment: string;
  created_at: string;
  updated_at: string;
};

export type AgentEvent = {
  event_id: number;
  run_id: string;
  event_type: string;
  timestamp: string;
  duration_ms: number | null;
  model: string | null;
  tool: string | null;
  status: string;
  error: string | null;
  details: Record<string, unknown>;
};

export type AgentRun = {
  run_id: string;
  status: string;
  service: string | null;
  diagnosis: string | null;
  user_request: string;
  evidence: Array<Record<string, unknown>>;
  hypotheses: Array<{ hypothesis: string; score: number; supporting_evidence?: Array<Record<string, unknown>>; contradicting_evidence?: Array<Record<string, unknown>> }>;
  knowledge_citations: Array<{ source: string; document: string; chunk: number; similarity: number; content: string }>;
  action_proposal: { action_type: string; target: string; reason: string; risk_level: string; status: string; evidence: Array<Record<string, unknown>> } | null;
  policy_decision: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
  events: AgentEvent[];
};

export type Approval = {
  id: number;
  run_id: string;
  action_id: string;
  requested_at: string;
  expires_at: string;
  decided_at: string | null;
  decision: "pending" | "approved" | "rejected" | "expired";
  decided_by: string | null;
  reason: string | null;
  proposal: {
    action_type: string;
    target: string;
    reason: string;
    risk_level: string;
    status: string;
    evidence: Array<Record<string, unknown>>;
  };
  execution_result: Record<string, unknown> | null;
};

export type Evaluation = {
  study: string;
  created_at: string;
  model_calls: number;
  limitations: string[];
  comparisons: Array<{
    component: string;
    experiment: string;
    scenario_count: number;
    metric: string[];
    result: Record<string, Record<string, number | string>>;
    difference: Record<string, number | string>;
    interpretation: string;
  }>;
};

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem("opspilot.token") ?? "";
}

export function getSession(): { token: string; username: string; role: string } | null {
  if (typeof window === "undefined") return null;
  const token = getToken();
  if (!token) return null;
  return {
    token,
    username: window.localStorage.getItem("opspilot.username") ?? "User",
    role: window.localStorage.getItem("opspilot.role") ?? "viewer",
  };
}

export async function api<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (authenticated) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") message = body.detail;
    } catch { /* retain status message */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function formatDate(value: string): string {
  return new Date(value).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function durationLabel(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}
