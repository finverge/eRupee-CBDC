import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import App from "./App"

describe("SovereignX Console", () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it("shows the login screen when no session is stored, with Sign in disabled until both fields are filled", () => {
    render(<App />)

    expect(screen.getByText("Finverge SovereignX")).toBeInTheDocument()
    const signIn = screen.getByRole("button", { name: /sign in/i })
    expect(signIn).toBeDisabled()

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "scheme.admin@sovereignx.dev" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "ChangeMe123!" } })
    expect(signIn).not.toBeDisabled()
  })

  it("clicking a demo account fills the form", () => {
    render(<App />)
    fireEvent.click(screen.getByText(/scheme.admin@sovereignx.dev/))
    expect(screen.getByLabelText("Email")).toHaveValue("scheme.admin@sovereignx.dev")
    expect(screen.getByLabelText("Password")).toHaveValue("ChangeMe123!")
  })

  it("submits credentials and renders the Dashboard shell after a successful login", async () => {
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (String(url).includes("/auth/login")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ access_token: "test-token", role: "scheme_administrator", full_name: "Test Admin" }),
        })
      }
      // Dashboard's own data fetch — shape matches sovereignx-core's DashboardOut schema.
      return Promise.resolve({
        ok: true,
        json: async () => ({
          beneficiaries_onboarded: 0, total_disbursed_paisa: 0, total_redeemed_paisa: 0,
          redemption_rate_pct: 0, open_alerts: 0,
          funnel: { eligible: 0, disbursed: 0, redeemed: 0, flagged: 0 },
          recent_batches: [], open_alert_list: [],
        }),
      })
    }))

    render(<App />)
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "scheme.admin@sovereignx.dev" } })
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "ChangeMe123!" } })
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }))

    expect(await screen.findByText("Dashboard")).toBeInTheDocument()
    expect(sessionStorage.getItem("sovereignx_session")).toBeTruthy()
  })
})
