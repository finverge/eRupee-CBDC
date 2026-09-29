import { useEffect, useState } from "react"
import { OFFLINE_QUEUE_CHANGED_EVENT, type OfflineWalletQueue } from "../offlineQueue"

export interface OfflineQueueStatusProps {
  queue: OfflineWalletQueue
  isOffline: boolean
  onSynced?: (results: { client_tx_id: string; outcome: string; executed: boolean }[]) => void
}

const inr = (paisa: number) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(paisa / 100)

/** Shows what's sitting in the on-device offline queue and lets the user
 * (or the app, automatically, on reconnect) trigger a sync. Nothing here
 * shows a cached balance — HLD 9.2/FSD FR-34 both forbid trusting a
 * locally-held balance figure. */
export function OfflineQueueStatus({ queue, isOffline, onSynced }: OfflineQueueStatusProps) {
  const [pending, setPending] = useState(queue.getQueue())
  const [syncing, setSyncing] = useState(false)
  const [lastResult, setLastResult] = useState<string | null>(null)

  function refresh() {
    setPending(queue.getQueue())
  }

  // Reacts to a payment queued by a sibling QuickPay instance, not just
  // this component's own sync() call — see OFFLINE_QUEUE_CHANGED_EVENT's
  // docstring for why localStorage's own "storage" event can't do this.
  useEffect(() => {
    window.addEventListener(OFFLINE_QUEUE_CHANGED_EVENT, refresh)
    return () => window.removeEventListener(OFFLINE_QUEUE_CHANGED_EVENT, refresh)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function doSync() {
    setSyncing(true)
    setLastResult(null)
    try {
      const results = await queue.sync()
      const allowed = results.filter((r) => r.executed).length
      const declined = results.length - allowed
      setLastResult(results.length === 0 ? "Nothing to sync." : `Synced ${results.length}: ${allowed} confirmed, ${declined} declined.`)
      onSynced?.(results)
    } finally {
      setSyncing(false)
      refresh()
    }
  }

  if (pending.length === 0 && !lastResult) return null

  return (
    <div className="sx-wallet sx-wallet-card" style={{ borderColor: pending.length > 0 ? "var(--sx-wallet-accent)" : undefined }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: "0.85rem", fontWeight: 600 }}>
          {pending.length > 0 ? `${pending.length} payment(s) queued offline` : "Offline queue"}
        </div>
        {!isOffline && pending.length > 0 && (
          <button
            onClick={doSync} disabled={syncing}
            style={{
              fontSize: "0.75rem", fontWeight: 600, padding: "0.3rem 0.6rem", borderRadius: "var(--sx-wallet-radius)",
              background: "var(--sx-wallet-primary)", color: "var(--sx-wallet-primary-foreground)", border: "none",
              cursor: syncing ? "wait" : "pointer",
            }}
          >
            {syncing ? "Syncing…" : "Sync Now"}
          </button>
        )}
      </div>
      {pending.length > 0 && (
        <div style={{ marginTop: "0.5rem" }}>
          {pending.map((p) => (
            <div key={p.client_tx_id} style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", padding: "0.2rem 0", color: "var(--sx-wallet-text-muted)" }}>
              <span>{p.merchant_ref}</span>
              <span>{inr(p.amount_paisa)} · pending sync</span>
            </div>
          ))}
        </div>
      )}
      {isOffline && pending.length > 0 && (
        <div style={{ fontSize: "0.75rem", color: "var(--sx-wallet-text-muted)", marginTop: "0.5rem" }}>
          Will sync automatically once back online.
        </div>
      )}
      {lastResult && <div style={{ fontSize: "0.8rem", marginTop: "0.5rem", color: "var(--sx-wallet-success)" }}>{lastResult}</div>}
    </div>
  )
}
