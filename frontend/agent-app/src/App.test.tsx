import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import App from "./App"

describe("Agent App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn())
  })

  it("shows the login screen with a disabled Sign In button until a password is entered", () => {
    render(<App />)

    expect(screen.getByText("SovereignX Agent")).toBeInTheDocument()
    const signIn = screen.getByRole("button", { name: /sign in/i })
    expect(signIn).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "ChangeMe123!" } })
    expect(signIn).not.toBeDisabled()
  })

  it("submits agent_ref and password to the login endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ agent_ref: "AGT-001", name: "Ravi Kumar", token: "test-token" }),
    })
    vi.stubGlobal("fetch", fetchMock)

    render(<App />)
    fireEvent.change(screen.getByPlaceholderText("Password"), { target: { value: "ChangeMe123!" } })
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }))

    await screen.findByText(/Ravi Kumar/)
    const [url, options] = fetchMock.mock.calls[0]
    expect(String(url)).toContain("/agents/AGT-001/login")
    expect(JSON.parse(options.body)).toEqual({ password: "ChangeMe123!" })
  })
})
