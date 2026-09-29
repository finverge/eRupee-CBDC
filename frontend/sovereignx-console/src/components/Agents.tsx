import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, Plus, Users, ArrowLeft } from "lucide-react"
import { api, ApiError, type Agent, type AgentDailySummary, type AgentTransaction, type AgentDailyReconciliation } from "@/lib/api"

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback
}
const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

interface Props {
  canManage: boolean
}

export function Agents({ canManage }: Props) {
  const [agents, setAgents] = useState<Agent[] | null>(null)
  const [summaries, setSummaries] = useState<Record<string, AgentDailySummary>>({})
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState<Agent | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    (async () => {
      setError(null)
      try {
        const list = await api.listAgents()
        setAgents(list)
        const entries = await Promise.all(
          list.map(async (a) => [a.agent_ref, await api.getAgentDailySummary(a.agent_ref).catch(() => null)] as const),
        )
        setSummaries(Object.fromEntries(entries.filter(([, s]) => s !== null)) as Record<string, AgentDailySummary>)
      } catch (e) {
        setError(errMsg(e, "Could not load agents — is erupee-ledger-simulator running on :8401?"))
      }
    })()
  }, [refreshKey])

  if (selected) {
    return <AgentDetail agent={selected} summary={summaries[selected.agent_ref]} onBack={() => setSelected(null)} />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><Users className="h-6 w-6" /> Agents</h1>
          <p className="text-sm text-muted-foreground mt-1">Banking Correspondent / CSC agents enabled for the assisted last-mile channel.</p>
        </div>
        {canManage && <Button onClick={() => setShowCreate((s) => !s)} className="gap-1.5"><Plus className="h-4 w-4" /> Onboard Agent</Button>}
      </div>

      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

      {showCreate && <CreateAgentForm onCreated={() => { setShowCreate(false); setRefreshKey((k) => k + 1) }} />}

      {agents === null ? <Skeleton className="h-64 w-full" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agents.map((a) => {
            const s = summaries[a.agent_ref]
            const usedPct = s ? Math.min(100, Math.round((s.total_amount_paisa / s.daily_limit_paisa) * 100)) : 0
            return (
              <Card key={a.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelected(a)}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle>{a.name}</CardTitle>
                    <Badge variant="secondary">{a.agent_ref}</Badge>
                  </div>
                  <CardDescription>{a.assigned_region}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-muted-foreground">Today's activity</span><span className="font-medium">{s ? `${s.transaction_count} txns · ${inr(s.total_amount_paisa)}` : "—"}</span></div>
                  <div className="flex justify-between"><span className="text-muted-foreground">Daily limit</span><span className="font-medium">{inr(a.daily_limit_paisa)}</span></div>
                  {s && (
                    <div className="pt-1">
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                        <div className="h-full rounded-full bg-primary" style={{ width: `${usedPct}%` }} />
                      </div>
                      <div className="text-xs text-muted-foreground mt-1">{usedPct}% of daily limit used · {inr(s.remaining_paisa)} remaining</div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
          {agents.length === 0 && <p className="text-sm text-muted-foreground col-span-2 py-8 text-center">No agents onboarded yet.</p>}
        </div>
      )}
    </div>
  )
}

function CreateAgentForm({ onCreated }: { onCreated: () => void }) {
  const [agentRef, setAgentRef] = useState("")
  const [name, setName] = useState("")
  const [region, setRegion] = useState("")
  const [limit, setLimit] = useState("50000")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true); setError(null)
    try {
      await api.createAgent({ agent_ref: agentRef, name, assigned_region: region, daily_limit_paisa: Math.round(parseFloat(limit) * 100), password })
      onCreated()
    } catch (e) {
      setError(errMsg(e, "Could not onboard agent."))
    } finally { setBusy(false) }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Onboard Agent</CardTitle><CardDescription>Registers a new Banking Correspondent / CSC agent for the assisted channel. The password is the agent's own login for the Agent App.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>Agent Reference</Label><Input value={agentRef} onChange={(e) => setAgentRef(e.target.value.toUpperCase())} placeholder="AGT-003" /></div>
          <div className="space-y-2"><Label>Full Name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Anita Desai (CSC Pune)" /></div>
          <div className="space-y-2"><Label>Assigned Region</Label><Input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="Pune" /></div>
          <div className="space-y-2"><Label>Daily Limit (₹)</Label><Input type="number" value={limit} onChange={(e) => setLimit(e.target.value)} /></div>
          <div className="space-y-2 col-span-2"><Label>Agent App Password</Label><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 6 characters" /></div>
        </div>
        <Button disabled={busy || !agentRef || !name || !region || password.length < 6} onClick={submit}>{busy ? "Onboarding…" : "Onboard Agent"}</Button>
      </CardContent>
    </Card>
  )
}

function AgentDetail({ agent, summary, onBack }: { agent: Agent; summary: AgentDailySummary | undefined; onBack: () => void }) {
  const [transactions, setTransactions] = useState<AgentTransaction[] | null>(null)
  const [reconHistory, setReconHistory] = useState<AgentDailyReconciliation[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      setError(null)
      try {
        const [txns, history] = await Promise.all([
          api.listAgentTransactions(agent.agent_ref),
          api.listAgentSummaryHistory(agent.agent_ref),
        ])
        setTransactions(txns)
        setReconHistory(history)
      } catch (e) {
        setError(errMsg(e, "Could not load transactions."))
      }
    })()
  }, [agent.agent_ref])

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to Agents
      </button>

      <div>
        <h1 className="text-2xl font-bold">{agent.name}</h1>
        <p className="text-sm text-muted-foreground mt-1">{agent.agent_ref} · {agent.assigned_region} · daily limit {inr(agent.daily_limit_paisa)}</p>
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg border p-4"><div className="text-xs uppercase text-muted-foreground">Today's Transactions</div><div className="text-2xl font-bold">{summary.transaction_count}</div></div>
          <div className="rounded-lg border p-4"><div className="text-xs uppercase text-muted-foreground">Today's Total</div><div className="text-2xl font-bold">{inr(summary.total_amount_paisa)}</div></div>
          <div className="rounded-lg border p-4"><div className="text-xs uppercase text-muted-foreground">Remaining Today</div><div className="text-2xl font-bold">{inr(summary.remaining_paisa)}</div></div>
        </div>
      )}

      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Daily Reconciliation History</CardTitle>
          <CardDescription>
            Persisted by Compliance → Run Reconciliation (FSD FR-31) — one row per day, updated in
            place if reconciliation runs again the same day. This is the settlement record; the
            live totals above refresh on every page load and may be ahead of the last pulled row.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr><th className="px-4 py-2">Date</th><th className="px-4 py-2">Transactions</th><th className="px-4 py-2">Total</th><th className="px-4 py-2">Last Pulled</th></tr>
            </thead>
            <tbody>
              {reconHistory === null ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">Loading…</td></tr>
              ) : reconHistory.length === 0 ? (
                <tr><td colSpan={4} className="px-4 py-6 text-center text-muted-foreground">Not reconciled yet — run reconciliation from the Compliance page.</td></tr>
              ) : reconHistory.map((r) => (
                <tr key={r.id} className="border-b last:border-0">
                  <td className="px-4 py-2">{r.date}</td>
                  <td className="px-4 py-2">{r.transaction_count}</td>
                  <td className="px-4 py-2">{inr(r.total_amount_paisa)}</td>
                  <td className="px-4 py-2 text-xs text-muted-foreground">{new Date(r.pulled_at).toLocaleString("en-IN")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Assisted Transactions</CardTitle><CardDescription>The underlying transactions each day's reconciliation row above summarizes.</CardDescription></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr><th className="px-4 py-2">Beneficiary</th><th className="px-4 py-2">Action</th><th className="px-4 py-2">Amount</th><th className="px-4 py-2">Merchant</th><th className="px-4 py-2">Result</th></tr>
            </thead>
            <tbody>
              {transactions === null ? (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">Loading…</td></tr>
              ) : transactions.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">No transactions yet.</td></tr>
              ) : transactions.map((t) => (
                <tr key={t.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{t.beneficiary_ref}</td>
                  <td className="px-4 py-2 capitalize">{t.action}</td>
                  <td className="px-4 py-2">{t.amount_paisa ? inr(t.amount_paisa) : "—"}</td>
                  <td className="px-4 py-2 font-mono text-xs">{t.merchant_ref ?? "—"}</td>
                  <td className="px-4 py-2"><Badge variant={t.executed ? "default" : "destructive"}>{t.executed ? "executed" : (t.rule_check_result ?? "declined").replace(/_/g, " ")}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}
