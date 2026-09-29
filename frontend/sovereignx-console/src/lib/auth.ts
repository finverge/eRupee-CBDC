const STORAGE_KEY = "sovereignx_session"

export interface Session {
  accessToken: string
  role: "platform_admin" | "scheme_administrator" | "compliance_officer" | "sponsor_bank_operator" | "agent"
  email: string
  fullName: string
}

export function getStoredSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

export function setStoredSession(session: Session) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session)) } catch { /* private-mode/blocked storage */ }
}

export function clearStoredSession() {
  try { sessionStorage.removeItem(STORAGE_KEY) } catch { /* nothing to clear */ }
}
