import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle } from "lucide-react"
import { api, ApiError, type DashboardData } from "@/lib/api"
import { StatTile, BarChart, STATUS } from "@/components/charts"

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback
}

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

const statusVariant: Record<string, "default" | "secondary" | "destructive"> = {
  confirmed: "default", processing: "secondary", queued: "secondary",
  partially_failed: "destructive", failed: "destructive",
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    (async () => {
      setLoading(true)
      setError(null)
      try {
        setData(await api.getDashboard())
      } catch (e) {
        setError(errMsg(e, "Could not load the dashboard."))
      } finally {
        setLoading(false)
      }
    })()
  }, [refreshKey])

  if (loading) return <Skeleton className="h-96 w-full" />
  if (error) return <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>
  if (!data) return null

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatTile label="Beneficiaries Onboarded" value={data.beneficiaries_onboarded} />
        <StatTile label="e₹ Disbursed" value={inr(data.total_disbursed_paisa)} />
        <StatTile label="Redemption Rate" value={`${data.redemption_rate_pct}%`} accent={STATUS.good} />
        <StatTile label="Open Compliance Alerts" value={data.open_alerts} accent={data.open_alerts > 0 ? STATUS.critical : undefined} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardHeader><CardTitle>Disbursement → Redemption Funnel</CardTitle></CardHeader>
          <CardContent>
            <BarChart data={[
              { label: "Eligible", value: data.funnel.eligible },
              { label: "Disbursed", value: data.funnel.disbursed },
              { label: "Redeemed", value: data.funnel.redeemed },
              { label: "Flagged", value: data.funnel.flagged, color: STATUS.critical },
            ]} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Compliance Queue</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {data.open_alert_list.length === 0 && <p className="text-sm text-muted-foreground py-4 text-center">No open alerts.</p>}
            {data.open_alert_list.map((a) => (
              <div key={a.id} className="flex items-start justify-between gap-2 border-b pb-2 last:border-0 last:pb-0">
                <div>
                  <div className="text-sm font-medium">{a.beneficiary_ref}</div>
                  <div className="text-xs text-muted-foreground">{a.rule_triggered}</div>
                </div>
                <Badge variant="destructive">{a.source}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Recent Disbursement Batches</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2">Batch</th><th className="px-4 py-2">District</th>
                <th className="px-4 py-2">Beneficiaries</th><th className="px-4 py-2">Amount</th><th className="px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.recent_batches.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{b.id.slice(0, 8)}</td>
                  <td className="px-4 py-2">{b.district ?? "All districts"}</td>
                  <td className="px-4 py-2">{b.confirmed_count} / {b.beneficiary_count}</td>
                  <td className="px-4 py-2">{inr(b.total_amount_paisa)}</td>
                  <td className="px-4 py-2"><Badge variant={statusVariant[b.status] ?? "secondary"}>{b.status.replace(/_/g, " ")}</Badge></td>
                </tr>
              ))}
              {data.recent_batches.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">No batches yet.</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <button className="text-xs text-muted-foreground hover:text-foreground underline underline-offset-2" onClick={() => setRefreshKey((k) => k + 1)}>
        Refresh
      </button>
    </div>
  )
}
