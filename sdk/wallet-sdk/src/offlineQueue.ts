/**
 * Offline transaction queue (FSD FR-26–FR-28, HLD 9.2). Queues signed
 * payment requests in localStorage while the device has no connectivity,
 * then syncs the whole batch to the ledger once it's back — see
 * erupee-ledger-simulator/app/routers/offline.py for the server side of
 * this contract (signature verification, idempotent client_tx_id, daily
 * caps enforced server-side, never trusted from the client alone).
 *
 * The device_secret used to sign each queued transaction is itself
 * stored in localStorage after registration — fine for a local dev
 * simulator; a real deployment would keep it in platform secure storage
 * (Keychain/Keystore), never plain localStorage.
 */
import { WalletApiClient, WalletApiError } from "./client"

const QUEUE_KEY = "sx_wallet_offline_queue"
const DEVICE_KEY = "sx_wallet_device"

export interface QueuedPayment {
  client_tx_id: string
  merchant_ref: string
  amount_paisa: number
  queued_at: string
  signature: string
}

interface DeviceRecord {
  device_id: string
  beneficiary_ref: string
  device_secret: string
  daily_cap_paisa: number
  daily_cap_count: number
}

function loadQueue(): QueuedPayment[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY)
    return raw ? (JSON.parse(raw) as QueuedPayment[]) : []
  } catch {
    return []
  }
}

/** Fired on `window` whenever the queue changes (payment queued, or sync
 * cleared it) — localStorage's own "storage" event only fires in OTHER
 * tabs, never the tab that made the write, so components in the same
 * page (e.g. OfflineQueueStatus) that need to react to a QuickPay in the
 * same tree must listen for this instead. */
export const OFFLINE_QUEUE_CHANGED_EVENT = "sx-wallet-offline-queue-changed"

function saveQueue(queue: QueuedPayment[]) {
  try { localStorage.setItem(QUEUE_KEY, JSON.stringify(queue)) } catch { /* storage unavailable — queue is lost, same as a device with no storage */ }
  window.dispatchEvent(new CustomEvent(OFFLINE_QUEUE_CHANGED_EVENT))
}

function loadDevice(): DeviceRecord | null {
  try {
    const raw = localStorage.getItem(DEVICE_KEY)
    return raw ? (JSON.parse(raw) as DeviceRecord) : null
  } catch {
    return null
  }
}

function saveDevice(device: DeviceRecord) {
  try { localStorage.setItem(DEVICE_KEY, JSON.stringify(device)) } catch { /* private-mode/blocked storage */ }
}

async function hmacSha256Hex(secret: string, message: string): Promise<string> {
  const enc = new TextEncoder()
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message))
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("")
}

export class OfflineWalletQueue {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  isDeviceRegistered(): boolean {
    return loadDevice() !== null
  }

  async registerDevice(beneficiaryRef: string): Promise<void> {
    const deviceId = `WEB-${crypto.randomUUID()}`
    const res = await fetch(`${this.baseUrl}/offline/devices/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: deviceId, beneficiary_ref: beneficiaryRef }),
    })
    if (!res.ok) throw new WalletApiError("Could not register this device for offline use", res.status)
    const data = await res.json()
    saveDevice({
      device_id: data.device_id, beneficiary_ref: beneficiaryRef, device_secret: data.device_secret,
      daily_cap_paisa: data.daily_cap_paisa, daily_cap_count: data.daily_cap_count,
    })
  }

  getDevice(): DeviceRecord | null {
    return loadDevice()
  }

  getQueue(): QueuedPayment[] {
    return loadQueue()
  }

  /** Queues a payment locally — call this instead of client.redeem() when
   * the app detects it has no connectivity. Returns the queued entry so
   * the UI can show it as "pending sync" immediately. */
  async queuePayment(merchantRef: string, amountPaisa: number): Promise<QueuedPayment> {
    const device = loadDevice()
    if (!device) throw new Error("No device registered — call registerDevice() first")

    const clientTxId = `OFFQ-${crypto.randomUUID()}`
    const queuedAt = new Date().toISOString()
    const signature = await hmacSha256Hex(device.device_secret, `${clientTxId}|${merchantRef}|${amountPaisa}|${queuedAt}`)
    const entry: QueuedPayment = { client_tx_id: clientTxId, merchant_ref: merchantRef, amount_paisa: amountPaisa, queued_at: queuedAt, signature }

    const queue = loadQueue()
    queue.push(entry)
    saveQueue(queue)
    return entry
  }

  /** Submits every queued payment to the ledger and clears entries the
   * server has now recorded (whatever the outcome — a rejected entry
   * doesn't belong back in the queue, it belongs in the UI's history as
   * "declined"). Call this when the app detects connectivity again. */
  async sync(): Promise<{ client_tx_id: string; outcome: string; executed: boolean }[]> {
    const device = loadDevice()
    const queue = loadQueue()
    if (!device || queue.length === 0) return []

    const res = await fetch(`${this.baseUrl}/offline/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ device_id: device.device_id, transactions: queue }),
    })
    if (!res.ok) throw new WalletApiError("Sync failed — will retry on next connectivity", res.status)
    const data = await res.json()
    saveQueue([]) // server has now durably recorded every entry (allowed, blocked, or capped) — nothing left to retry client-side
    return data.results
  }
}

export { WalletApiClient }
