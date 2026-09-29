import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { ArrowLeft, AlertCircle, Send, UserPlus } from "lucide-react"
import { api, ApiError, type Scheme, type Beneficiary, type DisbursementBatch } from "@/lib/api"

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback
}
const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

const eligBadge: Record<Beneficiary["eligibility_status"], "default" | "secondary" | "destructive"> = {
  eligible: "default", pending: "secondary", ineligible: "destructive",
}
const consentBadge: Record<Beneficiary["consent_status"], "default" | "secondary" | "destructive"> = {
  granted: "default", pending: "secondary", withdrawn: "destructive",
}

interface Props {
  scheme: Scheme
  canManage: boolean
  onBack: () => void
}

export function SchemeDetail({ scheme, canManage, onBack }: Props) {
  const [beneficiaries, setBeneficiaries] = useState<Beneficiary[]>([])
  const [batches, setBatches] = useState<DisbursementBatch[]>([])
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const [showIngest, setShowIngest] = useState(false)
  const [busyAction, setBusyAction] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      setError(null)
      try {
        const [b, batchList] = await Promise.all([
          api.listBeneficiaries(scheme.id),
          api.listBatches(scheme.id),
        ])
        setBeneficiaries(b)
        setBatches(batchList)
      } catch (e) {
        setError(errMsg(e, "Could not load scheme detail."))
      }
    })()
  }, [refreshKey, scheme.id])

  async function toggleStatus() {
    setBusyAction("status")
    try {
      await api.updateSchemeStatus(scheme.id, scheme.status === "active" ? "suspended" : "active")
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(errMsg(e, "Could not update status."))
    } finally {
      setBusyAction(null)
    }
  }

  async function grantConsent(beneficiaryId: string) {
    setBusyAction(beneficiaryId)
    try {
      await api.setConsent(scheme.id, beneficiaryId, "grant")
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(errMsg(e, "Could not record consent."))
    } finally {
      setBusyAction(null)
    }
  }

  async function disburse() {
    setBusyAction("disburse")
    try {
      await api.createBatch(scheme.id)
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setError(errMsg(e, "Disbursement failed."))
    } finally {
      setBusyAction(null)
    }
  }

  const eligibleGranted = beneficiaries.filter((b) => b.eligibility_status === "eligible" && b.consent_status === "granted").length

  return (
    <div className="space-y-4">
      <button onClick={onBack} className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to Schemes
      </button>

      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold">{scheme.name}</h1>
            <Badge>{scheme.status}</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">{scheme.department} · {inr(scheme.benefit_amount_paisa)} per beneficiary · lock: {scheme.permitted_merchant_categories.join(", ") || "none"}</p>
        </div>
        {canManage && (
          <Button variant="outline" disabled={busyAction === "status"} onClick={toggleStatus}>
            {scheme.status === "active" ? "Suspend" : "Activate"}
          </Button>
        )}
      </div>

      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Beneficiaries</CardTitle>
              <CardDescription>{beneficiaries.length} onboarded · {eligibleGranted} eligible + consented</CardDescription>
            </div>
            {canManage && <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setShowIngest((s) => !s)}><UserPlus className="h-4 w-4" /> Ingest</Button>}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {showIngest && <IngestForm schemeId={scheme.id} onDone={() => { setShowIngest(false); setRefreshKey((k) => k + 1) }} />}
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr><th className="px-3 py-2">Ref</th><th className="px-3 py-2">Name</th><th className="px-3 py-2">District</th><th className="px-3 py-2">Eligibility</th><th className="px-3 py-2">Consent</th><th className="px-3 py-2" /></tr>
            </thead>
            <tbody>
              {beneficiaries.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="px-3 py-2 font-mono text-xs">{b.beneficiary_ref}</td>
                  <td className="px-3 py-2">{b.full_name}</td>
                  <td className="px-3 py-2">{b.district}</td>
                  <td className="px-3 py-2"><Badge variant={eligBadge[b.eligibility_status]}>{b.eligibility_status}</Badge></td>
                  <td className="px-3 py-2"><Badge variant={consentBadge[b.consent_status]}>{b.consent_status}</Badge></td>
                  <td className="px-3 py-2">
                    {canManage && b.consent_status !== "granted" && (
                      <Button size="sm" variant="ghost" disabled={busyAction === b.id} onClick={() => grantConsent(b.id)}>Grant consent</Button>
                    )}
                  </td>
                </tr>
              ))}
              {beneficiaries.length === 0 && <tr><td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">No beneficiaries yet.</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Disbursement Batches</CardTitle>
            {canManage && (
              <Button size="sm" className="gap-1.5" disabled={busyAction === "disburse" || eligibleGranted === 0 || scheme.status !== "active"} onClick={disburse}>
                <Send className="h-4 w-4" /> {busyAction === "disburse" ? "Disbursing…" : `Disburse to ${eligibleGranted}`}
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
              <tr><th className="px-4 py-2">Batch</th><th className="px-4 py-2">Confirmed</th><th className="px-4 py-2">Failed</th><th className="px-4 py-2">Amount</th><th className="px-4 py-2">Status</th></tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id} className="border-b last:border-0">
                  <td className="px-4 py-2 font-mono text-xs">{b.id.slice(0, 8)}</td>
                  <td className="px-4 py-2">{b.confirmed_count}</td>
                  <td className="px-4 py-2">{b.failed_count}</td>
                  <td className="px-4 py-2">{inr(b.total_amount_paisa)}</td>
                  <td className="px-4 py-2"><Badge>{b.status.replace(/_/g, " ")}</Badge></td>
                </tr>
              ))}
              {batches.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-muted-foreground">No disbursement batches yet.</td></tr>}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  )
}

function IngestForm({ schemeId, onDone }: { schemeId: string; onDone: () => void }) {
  const [ref, setRef] = useState("")
  const [name, setName] = useState("")
  const [district, setDistrict] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await api.ingestBeneficiaries(schemeId, [{ beneficiary_ref: ref, full_name: name, district }])
      onDone()
    } catch (e) {
      setError(errMsg(e, "Could not ingest beneficiary."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-lg border p-4 space-y-3 bg-muted/20">
      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
      <div className="grid grid-cols-3 gap-3">
        <div className="space-y-1.5"><Label className="text-xs">Beneficiary ref</Label><Input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="BEN-001" /></div>
        <div className="space-y-1.5"><Label className="text-xs">Full name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ramesh Patil" /></div>
        <div className="space-y-1.5"><Label className="text-xs">District</Label><Input value={district} onChange={(e) => setDistrict(e.target.value)} placeholder="Nashik" /></div>
      </div>
      <Button size="sm" disabled={busy || !ref || !name || !district} onClick={submit}>{busy ? "Adding…" : "Add beneficiary"}</Button>
    </div>
  )
}
