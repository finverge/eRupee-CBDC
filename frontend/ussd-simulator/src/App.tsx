/**
 * USSD Simulator — plays the part of a telecom's USSD gateway forwarding
 * a *99#-style session to erupee-ledger-simulator's app/routers/ussd.py
 * (FSD FR-33–FR-34, HLD Section 9 Tier 2 "Feature Phone"). Styled like a
 * real feature-phone screen: monochrome, monospace, one small text block
 * per turn — nothing about this UI could show more than a real USSD
 * session ever could (HLD 9.2 constraint made visible, not just coded).
 */
import { useState, type CSSProperties } from "react"

const API_BASE = import.meta.env.VITE_LEDGER_BASE_URL ?? "http://localhost:8401"

interface UssdState {
  session_id: string
  screen_text: string
  awaiting_input: boolean
  session_ended: boolean
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...options?.headers } })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.detail ?? res.statusText)
  return body as T
}

export default function App() {
  const [session, setSession] = useState<UssdState | null>(null)
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [log, setLog] = useState<string[]>([])

  async function dial() {
    setBusy(true); setError(null)
    try {
      const s = await api<UssdState>("/ussd/dial", { method: "POST" })
      setSession(s)
      setLog([`> Dialed *99*46#`, s.screen_text])
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect")
    } finally { setBusy(false) }
  }

  async function send() {
    if (!session) return
    setBusy(true); setError(null)
    const typed = input
    try {
      const s = await api<UssdState>(`/ussd/${session.session_id}/input`, { method: "POST", body: JSON.stringify({ input: typed }) })
      setSession(s)
      setLog((l) => [...l, `> ${typed}`, s.screen_text])
      setInput("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Session error")
    } finally { setBusy(false) }
  }

  function endAndRestart() {
    setSession(null); setInput(""); setLog([]); setError(null)
  }

  return (
    <div style={{ minHeight: "100vh", background: "#2b2b2b", display: "flex", justifyContent: "center", alignItems: "center", padding: "1.5rem" }}>
      {/* Feature-phone chassis */}
      <div style={{ width: 280, background: "#1a1a1a", borderRadius: 24, padding: "1.2rem 1rem", boxShadow: "0 10px 40px rgba(0,0,0,0.5)" }}>
        <div style={{ textAlign: "center", color: "#888", fontSize: "0.6rem", marginBottom: "0.5rem", letterSpacing: 1 }}>SIMULATED FEATURE PHONE</div>

        {/* Monochrome LCD screen */}
        <div style={{
          background: "#c8d6b0", border: "3px solid #4a4a4a", borderRadius: 4, padding: "0.75rem",
          minHeight: 220, fontFamily: "'Courier New', monospace", fontSize: "0.8rem", color: "#1a2e0f",
          overflowY: "auto", maxHeight: 260,
        }}>
          {log.length === 0 && !session && (
            <div style={{ color: "#3a4a2a" }}>Press "Dial *99#" to start an e-Rupee USSD session.</div>
          )}
          {log.map((line, i) => (
            <div key={i} style={{ whiteSpace: "pre-wrap", marginBottom: "0.4rem", fontWeight: line.startsWith(">") ? 700 : 400 }}>{line}</div>
          ))}
          {session?.session_ended && <div style={{ marginTop: "0.5rem", color: "#5a3a1a" }}>— session ended —</div>}
        </div>

        {error && <div style={{ color: "#ff8080", fontSize: "0.7rem", marginTop: "0.5rem" }}>{error}</div>}

        <div style={{ marginTop: "0.75rem" }}>
          {!session ? (
            <button onClick={dial} disabled={busy} style={keyStyle("#2ecc71")}>{busy ? "Dialing…" : "Dial *99#"}</button>
          ) : session.session_ended ? (
            <button onClick={endAndRestart} style={keyStyle("#3498db")}>New Session</button>
          ) : (
            <div style={{ display: "flex", gap: "0.4rem" }}>
              <input
                value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && input && !busy && send()}
                placeholder="Reply…" autoFocus
                style={{
                  flex: 1, background: "#0f0f0f", color: "#c8d6b0", border: "1px solid #444", borderRadius: 6,
                  padding: "0.5rem", fontFamily: "'Courier New', monospace", fontSize: "0.85rem",
                }}
              />
              <button onClick={send} disabled={busy || !input} style={{ ...keyStyle("#2ecc71"), width: 70 }}>{busy ? "…" : "Send"}</button>
            </div>
          )}
        </div>

        <div style={{ textAlign: "center", color: "#555", fontSize: "0.6rem", marginTop: "0.6rem" }}>
          Try: BEN-CORE-001 → PIN 1234 → 1 (balance) or 2 (pay)
        </div>
      </div>
    </div>
  )
}

function keyStyle(bg: string): CSSProperties {
  return {
    width: "100%", padding: "0.6rem", border: "none", borderRadius: 8, background: bg, color: "#fff",
    fontWeight: 700, fontSize: "0.85rem", cursor: "pointer",
  }
}
