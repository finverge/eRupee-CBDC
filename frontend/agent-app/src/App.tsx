/**
 * SovereignX Agent App — the Banking Correspondent / CSC field app
 * (FSD FR-29–FR-32, HLD Section 9 Tier 3 "No Phone"). Finverge-branded
 * (agents work across schemes/banks, unlike the Wallet SDK which is
 * white-labeled per bank) — but every screen still surfaces the
 * beneficiary's own bank name prominently (FSD 9.6), so the beneficiary
 * can verify who actually holds their money, not just trust the agent.
 */
import { useState, type ReactNode } from "react"

const API_BASE = import.meta.env.VITE_LEDGER_BASE_URL ?? "http://localhost:8401"

type Step = "agent-login" | "lookup" | "otp-request" | "otp-verify" | "transact" | "result"

interface Balance { beneficiary_ref: string; balance_paisa: number; bank_name: string }
interface TxResult { rule_check_result: string | null; executed: boolean; amount_paisa: number | null; merchant_ref: string | null }

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(paisa / 100)

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...options?.headers } })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? res.statusText)
  return body as T
}

export default function App() {
  const [step, setStep] = useState<Step>("agent-login")
  const [agentRef, setAgentRef] = useState("AGT-001")
  const [agentPassword, setAgentPassword] = useState("")
  const [agentName, setAgentName] = useState("")
  const [agentToken, setAgentToken] = useState("")
  const [beneficiaryRef, setBeneficiaryRef] = useState("")
  const [balance, setBalance] = useState<Balance | null>(null)
  const [challengeId, setChallengeId] = useState("")
  const [simulatedCode, setSimulatedCode] = useState("")
  const [otpInput, setOtpInput] = useState("")
  const [sessionToken, setSessionToken] = useState("")
  const [action, setAction] = useState<"withdrawal" | "redemption">("withdrawal")
  const [merchantRef, setMerchantRef] = useState("")
  const [amount, setAmount] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<TxResult | null>(null)

  function authHeaders(): Record<string, string> {
    return { "X-Agent-Token": agentToken }
  }

  async function login() {
    setBusy(true); setError(null)
    try {
      const r = await api<{ agent_ref: string; name: string; token: string }>(`/agents/${agentRef}/login`, {
        method: "POST", body: JSON.stringify({ password: agentPassword }),
      })
      setAgentToken(r.token)
      setAgentName(r.name)
      setStep("lookup")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed")
    } finally { setBusy(false) }
  }

  function logout() {
    setStep("agent-login"); setAgentToken(""); setAgentName(""); setAgentPassword("")
    setBeneficiaryRef(""); setBalance(null); setOtpInput(""); setSessionToken("")
    setMerchantRef(""); setAmount(""); setResult(null); setError(null)
  }

  async function doLookup() {
    setBusy(true); setError(null)
    try {
      const b = await api<Balance>(`/agents/${agentRef}/lookup/${beneficiaryRef}`, { headers: authHeaders() })
      setBalance(b)
      setStep("otp-request")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lookup failed")
    } finally { setBusy(false) }
  }

  async function requestOtp() {
    setBusy(true); setError(null)
    try {
      const r = await api<{ challenge_id: string; simulated_code: string }>(`/agents/${agentRef}/otp/request`, {
        method: "POST", headers: authHeaders(), body: JSON.stringify({ beneficiary_ref: beneficiaryRef }),
      })
      setChallengeId(r.challenge_id)
      setSimulatedCode(r.simulated_code)
      setStep("otp-verify")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not request OTP")
    } finally { setBusy(false) }
  }

  async function verifyOtp() {
    setBusy(true); setError(null)
    try {
      const r = await api<{ verified: boolean; assisted_session_token?: string }>(`/agents/${agentRef}/otp/verify`, {
        method: "POST", headers: authHeaders(), body: JSON.stringify({ challenge_id: challengeId, code: otpInput }),
      })
      if (!r.verified || !r.assisted_session_token) {
        setError("Incorrect code — ask the beneficiary to re-check.")
        return
      }
      setSessionToken(r.assisted_session_token)
      setStep("transact")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Verification failed")
    } finally { setBusy(false) }
  }

  async function submitTransaction() {
    setBusy(true); setError(null)
    try {
      const paisa = Math.round(parseFloat(amount) * 100)
      const r = await api<TxResult>(`/agents/${agentRef}/assisted/transact`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          beneficiary_ref: beneficiaryRef, action, amount_paisa: paisa,
          merchant_ref: action === "redemption" ? merchantRef : undefined,
          assisted_session_token: sessionToken,
        }),
      })
      setResult(r)
      setStep("result")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Transaction failed")
    } finally { setBusy(false) }
  }

  function reset() {
    setStep("lookup"); setBeneficiaryRef(""); setBalance(null); setOtpInput(""); setSessionToken("")
    setMerchantRef(""); setAmount(""); setResult(null); setError(null)
  }

  return (
    <div style={{ minHeight: "100vh", background: "#0B2447", display: "flex", justifyContent: "center", padding: "1.5rem 1rem" }}>
      <div style={{ width: "100%", maxWidth: 380 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem", marginBottom: "1.5rem" }}>
          <div style={{ width: 38, height: 38, borderRadius: 8, background: "#1E8F6F", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800 }}>₹</div>
          <div>
            <div style={{ color: "#fff", fontWeight: 700, fontSize: "1rem" }}>SovereignX Agent</div>
            <div style={{ color: "#9FB3D6", fontSize: "0.7rem" }}>Banking Correspondent App</div>
          </div>
        </div>

        {step === "agent-login" && (
          <Card>
            <Label>Agent Reference</Label>
            <Input value={agentRef} onChange={setAgentRef} placeholder="AGT-001" />
            <Label>Password</Label>
            <Input value={agentPassword} onChange={setAgentPassword} placeholder="Password" type="password" />
            <Button onClick={login} disabled={busy || !agentRef || !agentPassword}>{busy ? "Signing in…" : "Sign In"}</Button>
          </Card>
        )}

        {step !== "agent-login" && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <div style={{ color: "#9FB3D6", fontSize: "0.75rem" }}>Agent: {agentName || agentRef} ({agentRef})</div>
            <button onClick={logout} style={{ background: "none", border: "none", color: "#9FB3D6", fontSize: "0.7rem", textDecoration: "underline", cursor: "pointer" }}>Sign out</button>
          </div>
        )}

        {step === "lookup" && (
          <Card>
            <Label>Beneficiary Reference</Label>
            <Input value={beneficiaryRef} onChange={setBeneficiaryRef} placeholder="BEN-CORE-001" />
            <Button onClick={doLookup} disabled={busy || !beneficiaryRef}>{busy ? "Looking up…" : "Look Up Balance"}</Button>
          </Card>
        )}

        {step === "otp-request" && balance && (
          <Card>
            <BankBanner bankName={balance.bank_name} />
            <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "0.75rem" }}>Balance</div>
            <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#0B2447" }}>{inr(balance.balance_paisa)}</div>
            <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: "1rem" }}>
              To move money, the beneficiary must confirm via a one-time code sent to their registered mobile.
            </div>
            <Button onClick={requestOtp} disabled={busy}>{busy ? "Sending…" : "Send Confirmation Code"}</Button>
          </Card>
        )}

        {step === "otp-verify" && (
          <Card>
            <BankBanner bankName={balance?.bank_name ?? ""} />
            <div style={{
              marginTop: "0.75rem", padding: "0.5rem 0.75rem", background: "#fef3c7", color: "#92400e",
              fontSize: "0.7rem", borderRadius: 6, fontWeight: 600,
            }}>
              SIMULATED SMS to beneficiary's phone: your code is {simulatedCode}
              <div style={{ fontWeight: 400, marginTop: "0.15rem" }}>(a real deployment never shows this to the agent — the beneficiary reads it off their own phone and tells the agent)</div>
            </div>
            <Label>Ask the beneficiary for their code</Label>
            <Input value={otpInput} onChange={setOtpInput} placeholder="6-digit code" />
            <Button onClick={verifyOtp} disabled={busy || otpInput.length !== 6}>{busy ? "Verifying…" : "Verify"}</Button>
          </Card>
        )}

        {step === "transact" && (
          <Card>
            <BankBanner bankName={balance?.bank_name ?? ""} />
            <div style={{ fontSize: "0.75rem", color: "#16a34a", fontWeight: 600, margin: "0.5rem 0" }}>✓ Beneficiary confirmed</div>
            <Label>Action</Label>
            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
              <PillButton active={action === "withdrawal"} onClick={() => setAction("withdrawal")}>Cash Withdrawal</PillButton>
              <PillButton active={action === "redemption"} onClick={() => setAction("redemption")}>Pay Merchant</PillButton>
            </div>
            {action === "redemption" && (
              <>
                <Label>Merchant Reference</Label>
                <Input value={merchantRef} onChange={setMerchantRef} placeholder="MER-001" />
              </>
            )}
            <Label>Amount (₹)</Label>
            <Input value={amount} onChange={setAmount} placeholder="500" type="number" />
            <Button onClick={submitTransaction} disabled={busy || !amount || (action === "redemption" && !merchantRef)}>
              {busy ? "Processing…" : "Confirm"}
            </Button>
          </Card>
        )}

        {step === "result" && result && (
          <Card>
            <BankBanner bankName={balance?.bank_name ?? ""} />
            <div style={{ textAlign: "center", padding: "1rem 0" }}>
              <div style={{ fontSize: "2rem" }}>{result.executed ? "✅" : "❌"}</div>
              <div style={{ fontWeight: 700, fontSize: "1.1rem", color: result.executed ? "#16a34a" : "#dc2626", marginTop: "0.5rem" }}>
                {result.executed ? "Transaction Successful" : "Transaction Declined"}
              </div>
              {!result.executed && result.rule_check_result && (
                <div style={{ fontSize: "0.8rem", color: "#6b7280", marginTop: "0.25rem" }}>
                  Reason: {result.rule_check_result.replace(/_/g, " ")}
                </div>
              )}
              {result.amount_paisa && <div style={{ fontSize: "0.9rem", marginTop: "0.5rem" }}>{inr(result.amount_paisa)}</div>}
            </div>
            <Button onClick={reset}>New Transaction</Button>
          </Card>
        )}

        {error && (
          <div style={{ marginTop: "0.75rem", padding: "0.6rem 0.8rem", background: "#fee2e2", color: "#991b1b", fontSize: "0.8rem", borderRadius: 8 }}>
            {error}
          </div>
        )}
      </div>
    </div>
  )
}

function Card({ children }: { children: ReactNode }) {
  return <div style={{ background: "#fff", borderRadius: 12, padding: "1.25rem", boxShadow: "0 4px 12px rgba(0,0,0,0.15)" }}>{children}</div>
}
function Label({ children }: { children: ReactNode }) {
  return <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#374151", marginBottom: "0.3rem", marginTop: "0.6rem" }}>{children}</div>
}
function Input({ value, onChange, placeholder, type = "text" }: { value: string; onChange: (v: string) => void; placeholder?: string; type?: string }) {
  return (
    <input
      value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} type={type}
      style={{ width: "100%", boxSizing: "border-box", border: "1px solid #d1d5db", borderRadius: 8, padding: "0.6rem 0.75rem", fontSize: "0.95rem" }}
    />
  )
}
function Button({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      onClick={onClick} disabled={disabled}
      style={{
        width: "100%", marginTop: "1rem", padding: "0.7rem", border: "none", borderRadius: 8, fontWeight: 700,
        background: disabled ? "#9ca3af" : "#1E8F6F", color: "#fff", cursor: disabled ? "not-allowed" : "pointer", fontSize: "0.95rem",
      }}
    >
      {children}
    </button>
  )
}
function PillButton({ children, active, onClick }: { children: ReactNode; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1, padding: "0.5rem", borderRadius: 999, border: active ? "2px solid #0B2447" : "1px solid #d1d5db",
        background: active ? "#0B2447" : "#fff", color: active ? "#fff" : "#374151", fontWeight: 600, fontSize: "0.8rem", cursor: "pointer",
      }}
    >
      {children}
    </button>
  )
}
function BankBanner({ bankName }: { bankName: string }) {
  return (
    <div style={{ fontSize: "0.7rem", color: "#6b7280", background: "#f3f4f6", borderRadius: 6, padding: "0.4rem 0.6rem" }}>
      This transaction is on the beneficiary's account at <strong>{bankName}</strong> — not held by the agent or this app.
    </div>
  )
}
