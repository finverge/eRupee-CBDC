import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import App from "./App"

describe("USSD Simulator", () => {
  it("shows the idle prompt before dialing", () => {
    render(<App />)
    expect(screen.getByText(/Press "Dial \*99#" to start/)).toBeInTheDocument()
  })

  it("dials, shows the server's welcome screen, then sends a reply", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "sess-1", screen_text: "Welcome to e-Rupee.\nEnter your beneficiary reference:", awaiting_input: true, session_ended: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: "sess-1", screen_text: "Enter your 4-digit PIN:", awaiting_input: true, session_ended: false }),
      })
    vi.stubGlobal("fetch", fetchMock)

    render(<App />)
    fireEvent.click(screen.getByRole("button", { name: /dial \*99#/i }))

    await screen.findByText(/Enter your beneficiary reference/)

    fireEvent.change(screen.getByPlaceholderText("Reply…"), { target: { value: "BEN-CORE-001" } })
    fireEvent.click(screen.getByRole("button", { name: /send/i }))

    await screen.findByText(/Enter your 4-digit PIN/)

    expect(fetchMock).toHaveBeenNthCalledWith(1, expect.stringContaining("/ussd/dial"), expect.objectContaining({ method: "POST" }))
    const secondCallBody = JSON.parse(fetchMock.mock.calls[1][1].body)
    expect(secondCallBody).toEqual({ input: "BEN-CORE-001" })
  })
})
