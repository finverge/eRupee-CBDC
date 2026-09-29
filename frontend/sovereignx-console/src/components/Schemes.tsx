import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, Plus } from "lucide-react"
import { api, ApiError, type Scheme } from "@/lib/api"
import { SchemeDetail } from "@/components/SchemeDetail"

function errMsg(e: unknown, fallback: string) {
  return e instanceof ApiError ? e.message : fallback
}

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

const statusVariant: Record<Scheme["status"], "default" | "secondary" | "destructive"> = {
  active: "default", draft: "secondary", suspended: "destructive", closed: "secondary",
}

interface Props {
  canManage: boolean
}

export function Schemes({ canManage }: Props) {
  const [schemes, setSchemes] = useState<Scheme[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [selected, setSelected] = useState<Scheme | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    (async () => {
      setError(null)
      try {
        setSchemes(await api.listSchemes())
      } catch (e) {
        setError(errMsg(e, "Could not load schemes."))
      }
    })()
  }, [refreshKey])

  if (selected) {
    return <SchemeDetail scheme={selected} canManage={canManage} onBack={() => { setSelected(null); setRefreshKey((k) => k + 1) }} />
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Schemes</h1>
          <p className="text-sm text-muted-foreground mt-1">Government subsidy / DBT schemes configured on SovereignX.</p>
        </div>
        {canManage && <Button onClick={() => setShowCreate((s) => !s)} className="gap-1.5"><Plus className="h-4 w-4" /> New Scheme</Button>}
      </div>

      {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}

      {showCreate && <CreateSchemeForm onCreated={() => { setShowCreate(false); setRefreshKey((k) => k + 1) }} />}

      {schemes === null ? <Skeleton className="h-64 w-full" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {schemes.map((s) => (
            <Card key={s.id} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => setSelected(s)}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle>{s.name}</CardTitle>
                  <Badge variant={statusVariant[s.status]}>{s.status}</Badge>
                </div>
                <CardDescription>{s.department}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-1 text-sm">
                <div className="flex justify-between"><span className="text-muted-foreground">Benefit amount</span><span className="font-medium">{inr(s.benefit_amount_paisa)}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Merchant lock</span><span className="font-medium">{s.permitted_merchant_categories.join(", ") || "None"}</span></div>
                <div className="flex justify-between"><span className="text-muted-foreground">Validity</span><span className="font-medium">{new Date(s.validity_start).toLocaleDateString()} – {new Date(s.validity_end).toLocaleDateString()}</span></div>
              </CardContent>
            </Card>
          ))}
          {schemes.length === 0 && <p className="text-sm text-muted-foreground col-span-2 py-8 text-center">No schemes yet — create one to get started.</p>}
        </div>
      )}
    </div>
  )
}

function CreateSchemeForm({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("")
  const [department, setDepartment] = useState("")
  const [amount, setAmount] = useState("")
  const [validityEnd, setValidityEnd] = useState("")
  const [categories, setCategories] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      await api.createScheme({
        name, department, benefit_amount_paisa: Math.round(parseFloat(amount) * 100),
        validity_start: new Date().toISOString(),
        validity_end: new Date(validityEnd).toISOString(),
        permitted_merchant_categories: categories.split(",").map((c) => c.trim().toUpperCase()).filter(Boolean),
        single_use: false,
      })
      onCreated()
    } catch (e) {
      setError(errMsg(e, "Could not create scheme."))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>New Scheme</CardTitle><CardDescription>Configures the programmable disbursement rules for this scheme.</CardDescription></CardHeader>
      <CardContent className="space-y-4">
        {error && <Alert variant="destructive"><AlertCircle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2"><Label>Scheme name</Label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Kharif Fertilizer Subsidy 2026" /></div>
          <div className="space-y-2"><Label>Department</Label><Input value={department} onChange={(e) => setDepartment(e.target.value)} placeholder="State Agriculture Dept." /></div>
          <div className="space-y-2"><Label>Benefit amount (₹ per beneficiary)</Label><Input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="5000" /></div>
          <div className="space-y-2"><Label>Validity end date</Label><Input type="date" value={validityEnd} onChange={(e) => setValidityEnd(e.target.value)} /></div>
          <div className="space-y-2 col-span-2">
            <Label>Permitted merchant categories (comma-separated, blank = no lock)</Label>
            <Input value={categories} onChange={(e) => setCategories(e.target.value)} placeholder="FERTILIZER" />
          </div>
        </div>
        <Button disabled={busy || !name || !department || !amount || !validityEnd} onClick={submit}>
          {busy ? "Creating…" : "Create Scheme"}
        </Button>
      </CardContent>
    </Card>
  )
}
