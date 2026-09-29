import { useEffect, useState } from "react"
import { WalletApiClient, WalletApiError, type WalletHistoryEvent } from "../client"

export interface TransactionHistoryProps {
  client: WalletApiClient
  beneficiaryRef: string
  limit?: number
}

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

export function TransactionHistory({ client, beneficiaryRef, limit = 10 }: TransactionHistoryProps) {
  const [events, setEvents] = useState<WalletHistoryEvent[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    client.getHistory(beneficiaryRef)
      .then((e) => !cancelled && setEvents(e))
      .catch((e) => !cancelled && setError(e instanceof WalletApiError ? e.message : "Could not load history"))
    return () => { cancelled = true }
  }, [client, beneficiaryRef])

  return (
    <div className="sx-wallet sx-wallet-card">
      <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: "0.75rem" }}>Recent Activity</div>
      {error && <div style={{ color: "var(--sx-wallet-danger)", fontSize: "0.85rem" }}>{error}</div>}
      {!error && events === null && <div style={{ fontSize: "0.85rem", color: "var(--sx-wallet-text-muted)" }}>Loading…</div>}
      {events && events.length === 0 && <div style={{ fontSize: "0.85rem", color: "var(--sx-wallet-text-muted)" }}>No transactions yet.</div>}
      {events && events.slice(0, limit).map((e, i) => (
        <div key={i} style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "0.5rem 0", borderTop: i > 0 ? "1px solid var(--sx-wallet-border)" : undefined,
        }}>
          <div>
            <div style={{ fontSize: "0.85rem", fontWeight: 500 }}>{e.label}</div>
            <div style={{ fontSize: "0.7rem", color: "var(--sx-wallet-text-muted)" }}>{new Date(e.at).toLocaleString("en-IN")}</div>
          </div>
          <div style={{ fontSize: "0.9rem", fontWeight: 600, color: e.type === "credit" ? "var(--sx-wallet-success)" : "var(--sx-wallet-text)" }}>
            {e.type === "credit" ? "+" : "−"}{inr(e.amount_paisa)}
          </div>
        </div>
      ))}
    </div>
  )
}
