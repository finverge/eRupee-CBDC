import { useEffect, useState } from "react"
import { WalletApiClient, WalletApiError, type WalletBalance } from "../client"

export interface WalletBalanceCardProps {
  client: WalletApiClient
  beneficiaryRef: string
  /** Bank's own display label for the wallet type — never "SovereignX". */
  label?: string
}

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 }).format(paisa / 100)

export function WalletBalanceCard({ client, beneficiaryRef, label = "Digital Rupee (e₹) Balance" }: WalletBalanceCardProps) {
  const [balance, setBalance] = useState<WalletBalance | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    client.getBalance(beneficiaryRef)
      .then((b) => !cancelled && setBalance(b))
      .catch((e) => !cancelled && setError(e instanceof WalletApiError ? e.message : "Could not load balance"))
    return () => { cancelled = true }
  }, [client, beneficiaryRef])

  return (
    <div className="sx-wallet sx-wallet-card">
      <div style={{ fontSize: "0.8rem", color: "var(--sx-wallet-text-muted)", fontWeight: 500 }}>{label}</div>
      {error ? (
        <div style={{ color: "var(--sx-wallet-danger)", fontSize: "0.9rem", marginTop: "0.5rem" }}>{error}</div>
      ) : balance ? (
        <div style={{ fontSize: "2rem", fontWeight: 700, marginTop: "0.35rem", color: "var(--sx-wallet-primary)" }}>
          {inr(balance.balance_paisa)}
        </div>
      ) : (
        <div style={{ height: "2.5rem", width: "60%", marginTop: "0.5rem", borderRadius: 6, background: "var(--sx-wallet-surface-muted)" }} />
      )}
    </div>
  )
}
