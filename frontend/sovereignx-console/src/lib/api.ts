/** API client for sovereignx-core (port 8402). This console never calls
 * erupee-ledger-simulator directly — all ledger-touching actions go
 * through sovereignx-core, same as the real e₹ Connector Adapter
 * boundary this console is standing in for. */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8402"

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

let activeToken: string | null = null
export function setActiveToken(token: string | null) {
  activeToken = token
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(activeToken ? { Authorization: `Bearer ${activeToken}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    const message = Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join("; ") : body.detail
    throw new ApiError(message ?? res.statusText, res.status)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ---------- Types (mirroring sovereignx-core/app/schemas.py) ----------
export interface Scheme {
  id: string; name: string; department: string; benefit_amount_paisa: number
  validity_start: string; validity_end: string; permitted_merchant_categories: string[]
  single_use: boolean; status: "draft" | "active" | "suspended" | "closed"
  created_by: string; created_at: string
}
export interface Beneficiary {
  id: string; scheme_id: string; beneficiary_ref: string; full_name: string; district: string
  eligibility_status: "pending" | "eligible" | "ineligible"; eligibility_reason: string | null
  consent_status: "pending" | "granted" | "withdrawn"; created_at: string
}
export interface DisbursementBatch {
  id: string; scheme_id: string; district: string | null
  status: "queued" | "processing" | "confirmed" | "partially_failed" | "failed"
  beneficiary_count: number; confirmed_count: number; failed_count: number
  total_amount_paisa: number; triggered_by: string; created_at: string
}
export interface ComplianceAlert {
  id: string; source: string; beneficiary_ref: string; rule_triggered: string; detail: string
  status: "open" | "reviewed" | "dismissed"; reviewed_by: string | null; created_at: string
}
export interface ReconciliationRecord {
  id: string; instruction_id: string; external_redemption_id: string; merchant_ref: string
  merchant_category: string; amount_paisa: number; match_status: string; rule_check_result: string; created_at: string
}
export interface DashboardData {
  beneficiaries_onboarded: number; total_disbursed_paisa: number; total_redeemed_paisa: number
  redemption_rate_pct: number; open_alerts: number
  funnel: { eligible: number; disbursed: number; redeemed: number; flagged: number }
  recent_batches: DisbursementBatch[]
  open_alert_list: ComplianceAlert[]
}
export interface Agent {
  id: string; agent_ref: string; name: string; assigned_region: string
  daily_limit_paisa: number; kyc_status: string; created_at: string
}
export interface AgentDailySummary {
  agent_ref: string; date: string; transaction_count: number
  total_amount_paisa: number; daily_limit_paisa: number; remaining_paisa: number
}
export interface AgentTransaction {
  id: string; agent_ref: string; beneficiary_ref: string; action: string
  amount_paisa: number | null; merchant_ref: string | null
  rule_check_result: string | null; executed: boolean; created_at: string
}
export interface AgentDailyReconciliation {
  id: string; agent_ref: string; date: string
  transaction_count: number; total_amount_paisa: number; daily_limit_paisa: number; pulled_at: string
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; role: Session["role"]; full_name: string }>("/auth/login", {
      method: "POST", body: JSON.stringify({ email, password }),
    }),

  getDashboard: () => request<DashboardData>("/dashboard"),

  listSchemes: () => request<Scheme[]>("/schemes"),
  createScheme: (payload: Omit<Scheme, "id" | "status" | "created_by" | "created_at">) =>
    request<Scheme>("/schemes", { method: "POST", body: JSON.stringify(payload) }),
  updateSchemeStatus: (schemeId: string, status: Scheme["status"]) =>
    request<Scheme>(`/schemes/${schemeId}/status`, { method: "PATCH", body: JSON.stringify({ status }) }),

  listBeneficiaries: (schemeId: string) => request<Beneficiary[]>(`/schemes/${schemeId}/beneficiaries`),
  ingestBeneficiaries: (schemeId: string, items: { beneficiary_ref: string; full_name: string; district: string }[]) =>
    request<Beneficiary[]>(`/schemes/${schemeId}/beneficiaries/ingest`, { method: "POST", body: JSON.stringify({ items }) }),
  setConsent: (schemeId: string, beneficiaryId: string, action: "grant" | "withdraw") =>
    request<Beneficiary>(`/schemes/${schemeId}/beneficiaries/${beneficiaryId}/consent`, {
      method: "POST", body: JSON.stringify({ action }),
    }),

  listBatches: (schemeId?: string) => request<DisbursementBatch[]>(`/disbursements${schemeId ? `?scheme_id=${schemeId}` : ""}`),
  createBatch: (schemeId: string, district?: string) =>
    request<DisbursementBatch>("/disbursements", { method: "POST", body: JSON.stringify({ scheme_id: schemeId, district }) }),

  runReconciliation: () => request<{ pulled: number; matched: number; blocked: number; new_alerts: number; agent_summaries_pulled: number }>("/reconciliation/run", { method: "POST" }),
  listReconciliationRecords: () => request<ReconciliationRecord[]>("/reconciliation/records"),
  listAgentSummaryHistory: (agentRef?: string) => request<AgentDailyReconciliation[]>(`/reconciliation/agent-summaries${agentRef ? `?agent_ref=${agentRef}` : ""}`),
  listAlerts: (status?: string) => request<ComplianceAlert[]>(`/reconciliation/alerts${status ? `?status=${status}` : ""}`),
  reviewAlert: (alertId: string, action: "review" | "dismiss") =>
    request<ComplianceAlert>(`/reconciliation/alerts/${alertId}/review`, { method: "POST", body: JSON.stringify({ action }) }),

  listAgents: () => request<Agent[]>("/agents"),
  createAgent: (payload: { agent_ref: string; name: string; assigned_region: string; daily_limit_paisa: number; password: string }) =>
    request<Agent>("/agents", { method: "POST", body: JSON.stringify(payload) }),
  getAgentDailySummary: (agentRef: string) => request<AgentDailySummary>(`/agents/${agentRef}/daily-summary`),
  listAgentTransactions: (agentRef: string) => request<AgentTransaction[]>(`/agents/${agentRef}/transactions`),
}

type Session = import("./auth").Session
