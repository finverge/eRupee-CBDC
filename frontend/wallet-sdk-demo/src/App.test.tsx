import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import App from "./App"

describe("Wallet SDK Demo", () => {
  beforeEach(() => {
    localStorage.clear()
    // Broad catch-all: this app's mount fires several real network calls
    // (device registration, balance, history) via the SDK's own
    // components — this smoke test only needs the shell to render
    // without crashing, not to assert on any one call's response shape.
    // getHistory() expects an array specifically; everything else gets {}.
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: async () => (String(url).includes("history") ? [] : {}),
    })))
  })

  it("renders the host bank's own branding, proving the SDK re-themes per host", async () => {
    render(<App />)
    expect(await screen.findByText("Sahyadri Grameen Bank")).toBeInTheDocument()
    expect(screen.getByRole("checkbox")).toBeInTheDocument()
    await screen.findByText("No transactions yet.") // let the child components' own fetches settle before the test ends
  })

  it("registers the device on mount when none is registered yet", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => Promise.resolve({
      ok: true,
      json: async () => (String(url).includes("history") ? [] : {}),
    }))
    vi.stubGlobal("fetch", fetchMock)

    render(<App />)

    await vi.waitFor(() => {
      const calledRegister = fetchMock.mock.calls.some(([url]) => String(url).includes("/offline/devices/register"))
      expect(calledRegister).toBe(true)
    })
  })
})
