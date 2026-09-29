import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { RefreshCw, AlertCircle, ShieldAlert } from "lucide-react"
import { api, ApiError, type ComplianceAlert } from "@/lib/api"
import { Skeleton } from "@/components/ui/skeleton"

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback
}

interface Props {
  canReview: boolean
}

export function Compliance({ canReview }: Props) {
  const [alerts, setAlerts] = useState<ComplianceAlert[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [runResult, setRunResult] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    (async () => {
      setError(null)
      try {
        setAlerts(await api.listAlerts())
      } catch (e) {
        setError(errMsg(e, "Could not load compliance alerts."))
      }
    })()
  }, [refreshKey])

  async function runReconciliation() {
    setBusy("run")
    setRunResult(null)
    setError(null)
    try {
      const r = await api.runReconciliation()
      setRunResult(`Pulled ${r.pulled} redemption event(s) — ${r.matched} matched, ${r.blocked} blocked, ${r.new_alerts} new alert(s) raised. Also reconciled ${r.agent_summaries_pulled} agent daily summar${r.agent_summaries_pulled === 1 ? "y" : "ies"}.`)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(errMsg(e, "Reconciliation run failed — is erupee-ledger-simulator running on :8401?"))
    } finally {
      setBusy(null)
    }
  }

  async function actOnAlert(id: string, action: "review" | "dismiss") {
    setBusy(id)
    try {
      await api.reviewAlert(id, action)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(errMsg(e, "Could not update alert."))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2"><ShieldAlert className="h-6 w-6" /> Compliance</h1>
          <p className="text-sm text-muted-foreground mt-1">Fraud360 / AML360 CBDC rule pack — pulls and evaluates redemption events from the ledger.</p>
        </div>
        <Button className="gap-1.5" disabled={busy === "run"} onClick={runReconciliation}>
          <RefreshCw className={`h-4 w-4 ${busy === "run" ? "animate-spin" : ""}`} /> Run Reconciliation
        </Button>
      </div>

      {runResult && <Alert><AlertDescription>{runResult}</AlertDescription></Alert>}
      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

      {alerts === null ? <Skeleton className="h-40 w-full" /> : (
      <Card>
        <CardHeader><CardTitle>Open Alerts</CardTitle><CardDescription>{alerts.filter((a) => a.status === "open").length} awaiting review</CardDescription></CardHeader>
        <CardContent className="space-y-3">
          {alerts.filter((a) => a.status === "open").map((a) => (
            <div key={a.id} className="rounded-lg border p-3 flex items-start justify-between gap-3">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-medium">{a.beneficiary_ref}</span>
                  <Badge variant="destructive">{a.source}</Badge>
                  <Badge variant="secondary">{a.rule_triggered}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{a.detail}</p>
              </div>
              {canReview && (
                <div className="flex gap-1.5 shrink-0">
                  <Button size="sm" variant="outline" disabled={busy === a.id} onClick={() => actOnAlert(a.id, "review")}>Mark reviewed</Button>
                  <Button size="sm" variant="ghost" disabled={busy === a.id} onClick={() => actOnAlert(a.id, "dismiss")}>Dismiss</Button>
                </div>
              )}
            </div>
          ))}
          {alerts.filter((a) => a.status === "open").length === 0 && (
            <p className="text-sm text-muted-foreground py-6 text-center">No open alerts. Run reconciliation to pull the latest redemption events.</p>
          )}
        </CardContent>
      </Card>
      )}
    </div>
  )
}
