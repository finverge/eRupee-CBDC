/**
 * WalletApiClient — the only network boundary this SDK has. Talks to the
 * sponsor bank's own e₹ ledger (erupee-ledger-simulator's /public/wallet/*
 * endpoints in this dev setup — see that service's public_wallet.py for
 * why these are open/unauthenticated here and what a real deployment must
 * add: the bank's own beneficiary-level auth, not a service key).
 *
 * The host bank app supplies its own baseUrl (its own backend or its own
 * proxy in front of its real core banking system) — this SDK never
 * hardcodes SovereignX's or any specific bank's URL.
 */
export interface WalletBalance {
  beneficiary_ref: string
  balance_paisa: number
}

export interface WalletHistoryEvent {
  type: "credit" | "debit"
  amount_paisa: number
  label: string
  at: string
}

export interface PermittedCategories {
  merchant_categories: string[] | null
  expires_at: string | null
}

export interface RedeemResult {
  id: string
  merchant_ref: string
  amount_paisa: number
  rule_check_result: string
  executed: boolean
}

export class WalletApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = "WalletApiError"
    this.status = status
  }
}

export class WalletApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...options?.headers },
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }))
      throw new WalletApiError(body.detail ?? res.statusText, res.status)
    }
    return res.json() as Promise<T>
  }

  getBalance(beneficiaryRef: string) {
    return this.request<WalletBalance>(`/public/wallet/${encodeURIComponent(beneficiaryRef)}`)
  }

  getHistory(beneficiaryRef: string) {
    return this.request<WalletHistoryEvent[]>(`/public/wallet/${encodeURIComponent(beneficiaryRef)}/history`)
  }

  getPermittedCategories(beneficiaryRef: string) {
    return this.request<PermittedCategories>(`/public/wallet/${encodeURIComponent(beneficiaryRef)}/permitted-categories`)
  }

  redeem(beneficiaryRef: string, merchantRef: string, amountPaisa: number) {
    return this.request<RedeemResult>(`/public/wallet/${encodeURIComponent(beneficiaryRef)}/redeem`, {
      method: "POST",
      body: JSON.stringify({ beneficiary_ref: beneficiaryRef, merchant_ref: merchantRef, amount_paisa: amountPaisa }),
    })
  }
}
