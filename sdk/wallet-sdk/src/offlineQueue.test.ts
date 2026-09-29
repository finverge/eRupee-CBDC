/**
 * The client side of the exact signature contract erupee-ledger-simulator/
 * app/routers/offline.py::_verify_signature checks server-side. A
 * previous version of the server code broke this by re-serializing the
 * parsed timestamp before verifying — these tests lock in the message
 * format (pipe-delimited, queued_at as the exact string that gets
 * signed) from the client's side of that contract.
 */
import { describe, it, expect, beforeEach, vi } from "vitest"
import { OfflineWalletQueue, OFFLINE_QUEUE_CHANGED_EVENT } from "./offlineQueue"

const DEVICE_KEY = "sx_wallet_device"
const QUEUE_KEY = "sx_wallet_offline_queue"

async function hmacSha256Hex(secret: string, message: string): Promise<string> {
  const enc = new TextEncoder()
  const key = await crypto.subtle.importKey("raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(message))
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("")
}

function seedDevice(deviceSecret = "test-device-secret") {
  localStorage.setItem(DEVICE_KEY, JSON.stringify({
    device_id: "DEV-TEST", beneficiary_ref: "BEN-001", device_secret: deviceSecret,
    daily_cap_paisa: 200000, daily_cap_count: 5,
  }))
}

describe("OfflineWalletQueue", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("queuePayment signs exactly client_tx_id|merchant_ref|amount_paisa|queued_at", async () => {
    seedDevice("test-device-secret")
    const queue = new OfflineWalletQueue("http://localhost:8401")

    const entry = await queue.queuePayment("MER-001", 5000)

    const expectedMessage = `${entry.client_tx_id}|MER-001|5000|${entry.queued_at}`
    const expectedSignature = await hmacSha256Hex("test-device-secret", expectedMessage)
    expect(entry.signature).toBe(expectedSignature)
  })

  it("throws if no device is registered yet", async () => {
    const queue = new OfflineWalletQueue("http://localhost:8401")
    await expect(queue.queuePayment("MER-001", 5000)).rejects.toThrow(/No device registered/)
  })

  it("persists queued payments and getQueue() reflects them", async () => {
    seedDevice()
    const queue = new OfflineWalletQueue("http://localhost:8401")

    await queue.queuePayment("MER-001", 1000)
    await queue.queuePayment("MER-002", 2000)

    expect(queue.getQueue()).toHaveLength(2)
    expect(localStorage.getItem(QUEUE_KEY)).toContain("MER-001")
  })

  it("dispatches OFFLINE_QUEUE_CHANGED_EVENT on the window when a payment is queued", async () => {
    seedDevice()
    const queue = new OfflineWalletQueue("http://localhost:8401")
    const handler = vi.fn()
    window.addEventListener(OFFLINE_QUEUE_CHANGED_EVENT, handler)

    await queue.queuePayment("MER-001", 1000)

    expect(handler).toHaveBeenCalledTimes(1)
  })

  it("each queued payment gets a unique client_tx_id (idempotency key)", async () => {
    seedDevice()
    const queue = new OfflineWalletQueue("http://localhost:8401")

    const first = await queue.queuePayment("MER-001", 1000)
    const second = await queue.queuePayment("MER-001", 1000)

    expect(first.client_tx_id).not.toBe(second.client_tx_id)
  })

  it("sync() clears the local queue and returns the server's results", async () => {
    seedDevice()
    const queue = new OfflineWalletQueue("http://localhost:8401")
    await queue.queuePayment("MER-001", 1000)

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ results: [{ client_tx_id: "whatever", outcome: "allowed", executed: true }] }),
    }))

    const results = await queue.sync()

    expect(results).toHaveLength(1)
    expect(queue.getQueue()).toHaveLength(0)
  })

  it("sync() with an empty queue does not call fetch at all", async () => {
    seedDevice()
    const queue = new OfflineWalletQueue("http://localhost:8401")
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    const results = await queue.sync()

    expect(results).toEqual([])
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
