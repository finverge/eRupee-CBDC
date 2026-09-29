import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"
import { api, ApiError, setActiveToken } from "@/lib/api"
import type { Session } from "@/lib/auth"

interface Props {
  onSignedIn: (session: Session) => void
}

const DEMO_ACCOUNTS = [
  { email: "scheme.admin@sovereignx.dev", role: "Scheme Administrator" },
  { email: "compliance@sovereignx.dev", role: "Compliance Officer" },
  { email: "bank.ops@sovereignx.dev", role: "Sponsor Bank Operator" },
  { email: "admin@sovereignx.dev", role: "Platform Admin" },
]

export function Login({ onSignedIn }: Props) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function signIn() {
    setBusy(true)
    setError(null)
    try {
      const { access_token, role, full_name } = await api.login(email, password)
      setActiveToken(access_token)
      onSignedIn({ accessToken: access_token, role, email, fullName: full_name })
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sign-in failed — is sovereignx-core running on :8402?")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-secondary via-background to-secondary p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex flex-col items-center gap-3">
          <div className="text-2xl font-heading font-bold text-primary">Finverge SovereignX</div>
          <p className="text-sm text-muted-foreground text-center">
            Scheme Administrator Console — Government & Subsidy Orchestration + Retail Banking
          </p>
        </div>

        <Card className="shadow-lg">
          <CardHeader>
            <CardTitle>Sign in</CardTitle>
            <CardDescription>Enter your SovereignX console credentials.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {error && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && email && password && signIn()}
              />
            </div>
            <Button className="w-full" disabled={busy || !email || !password} onClick={signIn}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </CardContent>
        </Card>

        <div className="text-xs text-center text-muted-foreground space-y-1.5">
          <p className="font-medium">Demo accounts (password: ChangeMe123!)</p>
          {DEMO_ACCOUNTS.map((a) => (
            <button
              key={a.email}
              type="button"
              className="block w-full font-mono hover:text-foreground hover:underline underline-offset-2"
              onClick={() => { setEmail(a.email); setPassword("ChangeMe123!") }}
            >
              {a.email} — {a.role}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
