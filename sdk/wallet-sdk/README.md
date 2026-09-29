# @finverge/sovereignx-wallet-sdk

Embeddable, themeable e₹ wallet components for a sponsor bank/NBFC's own
app (FSD Section 6, "Module: Wallet SDK & Merchant Enablement", Release 1).

**This SDK never shows SovereignX branding.** It ships as unstyled
primitives that inherit the host bank's own colors, logo and typography
via a CSS custom-property theming contract (FSD Section 9.6) — the same
"swap a stylesheet, not a component" pattern Finverge uses for its own
internal LOS console theme.

## What's in here

- `client.ts` — `WalletApiClient`, the only network boundary. Talks to
  the sponsor bank's own e₹ ledger (in this dev setup,
  `erupee-ledger-simulator`'s `/public/wallet/*` endpoints — see that
  service's `app/routers/public_wallet.py` for why those are
  unauthenticated in this simulator and what a real deployment must add).
- `components/WalletBalanceCard.tsx` — balance display.
- `components/TransactionHistory.tsx` — recent credits/debits.
- `components/QuickPay.tsx` — merchant QR payment, showing the sponsor
  bank's real-time programmable-rule enforcement result (expiry,
  merchant-category lock, balance).
- `theme.css` — the `--sx-wallet-*` variable contract, with neutral
  (non-SovereignX) defaults.

## Embedding in a bank's app

**Import order matters.** `theme.css` must load *before* your own brand
override stylesheet — both declare the same `--sx-wallet-*` variables on
`:root`, and CSS resolves a tie between equal-specificity rules by source
order, so whichever loads last wins. Import the SDK's `theme.css` at your
app's entry point (before your own global CSS), not inside a component
that might load after your override — see `frontend/wallet-sdk-demo/src/
main.tsx` in this repo, which got this backwards on the first pass and
silently kept the SDK's default blue instead of the demo bank's purple
until the import order was fixed.

```tsx
import { WalletApiClient, WalletBalanceCard, TransactionHistory, QuickPay } from "@finverge/sovereignx-wallet-sdk"
import "@finverge/sovereignx-wallet-sdk/theme.css"  // load first, before your own brand CSS

// 1. Point at YOUR bank's own e₹ ledger endpoint (never SovereignX's URL).
const client = new WalletApiClient("https://api.yourbank.example/erupee")

// 2. Override the theme contract to your own brand — e.g. in your app's
//    global stylesheet, scoped however you like:
//
//    :root {
//      --sx-wallet-primary: #7c2d92;      /* your brand color */
//      --sx-wallet-accent: #f97316;
//      --sx-wallet-font: "Your Brand Font", sans-serif;
//    }

function WalletScreen({ beneficiaryRef }: { beneficiaryRef: string }) {
  return (
    <div>
      <WalletBalanceCard client={client} beneficiaryRef={beneficiaryRef} label="My Bank e₹ Wallet" />
      <QuickPay client={client} beneficiaryRef={beneficiaryRef} onPaid={() => {/* refresh balance */}} />
      <TransactionHistory client={client} beneficiaryRef={beneficiaryRef} />
    </div>
  )
}
```

See `frontend/wallet-sdk-demo/` in this repo for a runnable example that
themes these exact components with a different (non-SovereignX) bank
brand, proving the contract works without touching component code.

## What this SDK deliberately does NOT do

- Hold or custody e₹ — every balance/history/payment call reads from or
  writes to the sponsor bank's own ledger; this SDK is a thin client.
- Perform KYC — the host bank's own login/session already establishes
  who `beneficiaryRef` is; this SDK is handed that reference, not raw
  identity data.
- Implement offline queuing, USSD, or agent-assisted flows yet — those
  are separate Release 1 channels (FSD Sections 6.2–6.4), not part of
  this SDK's current component set.
