import { useEffect, useState, type CSSProperties } from "react"
import { WalletApiClient, WalletApiError, type PermittedCategories } from "../client"
import type { OfflineWalletQueue } from "../offlineQueue"

export interface QuickPayProps {
  client: WalletApiClient
  beneficiaryRef: string
  onPaid?: () => void
  /** When set and `isOffline` is true, payments queue locally instead of
   * hitting the network (FSD FR-26) — pass the same instance across
   * renders (e.g. from a parent ref/state), not a fresh one each time. */
  offlineQueue?: OfflineWalletQueue
  isOffline?: boolean
}

/** Simulates scanning a merchant's e₹ QR from inside the wallet app —
 * a real SDK would open a camera scanner; merchant_ref is typed here
 * instead since this is a demo. The rule check (expiry / merchant-
 * category lock / balance) happens on the sponsor bank's ledger, not in
 * this component — this UI only shows the outcome it's told. */
export function QuickPay({ client, beneficiaryRef, onPaid, offlineQueue, isOffline }: QuickPayProps) {
  const [merchantRef, setMerchantRef] = useState("")
  const [amount, setAmount] = useState("")
  const [permitted, setPermitted] = useState<PermittedCategories | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  useEffect(() => {
    if (isOffline) return // no network read while offline — the lock info shown was fetched before going offline
    client.getPermittedCategories(beneficiaryRef).then(setPermitted).catch(() => setPermitted(null))
  }, [client, beneficiaryRef, isOffline])

  async function pay() {
    setBusy(true)
    setResult(null)
    try {
      const paisa = Math.round(parseFloat(amount) * 100)

      if (isOffline && offlineQueue) {
        await offlineQueue.queuePayment(merchantRef, paisa)
        setResult({ ok: true, message: `Payment of ₹${amount} to ${merchantRef} queued — will sync and confirm when back online.` })
        onPaid?.()
        setMerchantRef(""); setAmount("")
        return
      }

      const res = await client.redeem(beneficiaryRef, merchantRef, paisa)
      if (res.executed) {
        setResult({ ok: true, message: `Payment of ₹${amount} to ${merchantRef} successful.` })
        onPaid?.()
      } else {
        setResult({ ok: false, message: `Payment declined: ${res.rule_check_result.replace(/_/g, " ")}.` })
      }
      setMerchantRef(""); setAmount("")
    } catch (e) {
      setResult({ ok: false, message: e instanceof WalletApiError ? e.message : "Payment failed." })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sx-wallet sx-wallet-card">
      <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.5rem" }}>
        Pay a Merchant
        {isOffline && (
          <span style={{
            marginLeft: "0.5rem", fontSize: "0.65rem", fontWeight: 700, padding: "0.1rem 0.4rem",
            borderRadius: 999, background: "var(--sx-wallet-danger)", color: "#fff", verticalAlign: "middle",
          }}>OFFLINE</span>
        )}
      </div>
      {permitted?.merchant_categories && (
        <div style={{ fontSize: "0.75rem", color: "var(--sx-wallet-text-muted)", marginBottom: "0.75rem" }}>
          This e₹ can only be spent at: {permitted.merchant_categories.join(", ")}
          {permitted.expires_at && ` · expires ${new Date(permitted.expires_at).toLocaleDateString("en-IN")}`}
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        <input
          placeholder="Merchant QR ref (e.g. MER-001)" value={merchantRef} onChange={(e) => setMerchantRef(e.target.value)}
          style={inputStyle}
        />
        <input
          placeholder="Amount (₹)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
          style={inputStyle}
        />
        <button
          disabled={busy || !merchantRef || !amount}
          onClick={pay}
          style={{
            background: "var(--sx-wallet-accent)", color: "var(--sx-wallet-primary-foreground)",
            border: "none", borderRadius: "var(--sx-wallet-radius)", padding: "0.6rem", fontWeight: 600,
            cursor: busy ? "wait" : "pointer", opacity: busy || !merchantRef || !amount ? 0.6 : 1,
          }}
        >
          {busy ? "Processing…" : isOffline ? "Queue Payment (Offline)" : "Pay"}
        </button>
      </div>
      {result && (
        <div style={{ marginTop: "0.75rem", fontSize: "0.85rem", color: result.ok ? "var(--sx-wallet-success)" : "var(--sx-wallet-danger)" }}>
          {result.message}
        </div>
      )}
    </div>
  )
}

const inputStyle: CSSProperties = {
  border: "1px solid var(--sx-wallet-border)", borderRadius: "var(--sx-wallet-radius)",
  padding: "0.5rem 0.75rem", fontSize: "0.9rem", fontFamily: "inherit",
}
