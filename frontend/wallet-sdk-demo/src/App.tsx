/**
 * Demo host app for @finverge/sovereignx-wallet-sdk — plays the part of a
 * SPONSOR BANK'S OWN app embedding the SDK. Deliberately themed in a
 * completely different brand (purple/amber "Sahyadri Grameen Bank", a
 * fictional regional bank) to prove the SDK's theming contract actually
 * re-skins every component with zero changes to the SDK's own source —
 * see ../../sdk/wallet-sdk/README.md.
 */
import { useEffect, useRef, useState } from "react"
import { WalletApiClient, WalletBalanceCard, TransactionHistory, QuickPay, OfflineQueueStatus, OfflineWalletQueue } from "@sdk/index"
// theme.css is imported in main.tsx, BEFORE index.css — the bank's own
// brand override in index.css must load after the SDK's defaults for the
// CSS cascade to let it win (see README.md's embedding order note).

const LEDGER_BASE_URL = import.meta.env.VITE_LEDGER_BASE_URL ?? "http://localhost:8401"
const client = new WalletApiClient(LEDGER_BASE_URL)

export default function App() {
  const [beneficiaryRef] = useState("BEN-CORE-001")
  const [refreshKey, setRefreshKey] = useState(0)
  const [isOffline, setIsOffline] = useState(false)
  const [deviceReady, setDeviceReady] = useState(false)
  const queueRef = useRef(new OfflineWalletQueue(LEDGER_BASE_URL))

  useEffect(() => {
    const queue = queueRef.current
    if (queue.isDeviceRegistered()) {
      setDeviceReady(true)
      return
    }
    queue.registerDevice(beneficiaryRef).then(() => setDeviceReady(true)).catch(() => setDeviceReady(false))
  }, [beneficiaryRef])

  return (
    <div style={{ minHeight: "100vh", background: "#faf5ff", padding: "2rem 1rem" }}>
      <div style={{ maxWidth: 420, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10, background: "var(--sx-wallet-primary)",
              color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: "1.1rem",
            }}>SG</div>
            <div>
              <div style={{ fontWeight: 700, fontSize: "1.05rem", color: "#1f1147" }}>Sahyadri Grameen Bank</div>
              <div style={{ fontSize: "0.75rem", color: "#6b5b95" }}>e₹ Digital Rupee Wallet</div>
            </div>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", fontSize: "0.75rem", color: "#6b5b95", cursor: "pointer" }}>
            <input type="checkbox" checked={isOffline} onChange={(e) => setIsOffline(e.target.checked)} />
            Simulate offline
          </label>
        </div>

        {isOffline && (
          <div style={{ background: "#fef3c7", color: "#92400e", fontSize: "0.75rem", fontWeight: 600, borderRadius: 8, padding: "0.5rem 0.75rem", marginBottom: "1rem", textAlign: "center" }}>
            No connectivity — payments will queue on this device
          </div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {!isOffline && <WalletBalanceCard key={`bal-${refreshKey}`} client={client} beneficiaryRef={beneficiaryRef} label="Your e₹ Balance" />}

          {deviceReady && (
            <QuickPay
              client={client} beneficiaryRef={beneficiaryRef}
              isOffline={isOffline} offlineQueue={queueRef.current}
              onPaid={() => setRefreshKey((k) => k + 1)}
            />
          )}

          {deviceReady && (
            <OfflineQueueStatus
              queue={queueRef.current} isOffline={isOffline}
              onSynced={() => setRefreshKey((k) => k + 1)}
            />
          )}

          {!isOffline && <TransactionHistory key={`hist-${refreshKey}`} client={client} beneficiaryRef={beneficiaryRef} />}
        </div>

        <p style={{ fontSize: "0.7rem", color: "#9083b8", textAlign: "center", marginTop: "1.5rem" }}>
          Powered by Finverge SovereignX (not shown to end users) · Try BEN-CORE-001 at MER-001 (allowed) or MER-002 (blocked — wrong merchant category) · Toggle "Simulate offline" to queue a payment, then untick and hit Sync Now
        </p>
      </div>
    </div>
  )
}
