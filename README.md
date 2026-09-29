# Finverge SovereignX — Release 1

Government & Subsidy Orchestration + Retail Banking, built together (see
`D:\Finverge\Docs\Products\eRupee-CBDC\BRD\Finverge_SovereignX_BRD_v1.2.docx`
and the accompanying FSD/HLD for the full spec this implements).

Same theme, component conventions, and service patterns as Mandate360
(`D:\Finverge\Code\DLP\LOS`) — dark-navy sidebar shell, shadcn/ui +
Tailwind v4 with a shared CSS-variable token system, FastAPI + SQLAlchemy
+ Postgres services — deliberately kept as a **separate codebase** from
LOS (CBDC is a different product line from NACH/lending), not a fork.

## What's real vs. simulated — read this first

- **Real:** every service below is genuinely running code — real Postgres
  tables, real HTTP APIs, real JWT auth, real rule enforcement, a real
  React console, a real embeddable SDK. Nothing described here is a mock
  UI wired to fake data.
- **Simulated, honestly:** `erupee-ledger-simulator` stands in for a
  sponsor bank's core banking system + its RBI CBDC ledger connectivity —
  **neither exists for this codebase to connect to**. It implements the
  same contract a real e₹ Connector Adapter would (HLD Section 4.3), so
  swapping it for a real bank integration later is a config change in
  `sovereignx-core/app/services/ledger_client.py`, not a rewrite.
- **Simulated, honestly:** the Fraud360/AML360 CBDC rule pack
  (`sovereignx-core/app/services/compliance.py`) and ConsentBridge consent
  capture are real, running rule logic — not fabricated connections to
  the actual Fraud360/AML360/ConsentBridge products, which this codebase
  holds no credentials for.
- **Simulated, honestly:** OTP delivery in the agent-assisted channel
  (`erupee-ledger-simulator/app/routers/agents.py`) — the simulator
  generates a 6-digit code and returns it directly in the API response
  instead of sending an SMS, since no SMS gateway exists here. Every place
  this happens is labeled "SIMULATED SMS" in the UI itself, not just in
  code comments.
- **Everything listed as "not yet built" in earlier versions of this
  README is now built**: Docker Compose and an automated test suite (87
  tests across both backends, all 4 frontends, and the SDK — see "Running
  the tests" below). No CI pipeline still — this isn't a git repository.

## Recently closed gaps

- **Unattended reconciliation:** `sovereignx-core` now runs an in-process
  background loop (`app/main.py`'s `_reconciliation_loop`, same pattern as
  Mandate360's `nach-tenant-admin` regulatory-watch loop) that calls the
  same `run_reconciliation_cycle()` the Compliance page's "Run
  Reconciliation" button calls, every `reconciliation_loop_interval_seconds`
  (default 120s, deliberately short for a local demo — FSD FR-31 describes
  a daily cycle). The manual button still works for on-demand runs. A real
  deployment can keep the loop, shorten/lengthen the interval, or drop it
  and point an external cron at `POST /reconciliation/run` instead.
- **Agent authentication:** the Agent App and USSD channel each had a real
  gap closed:
  - **Agent App** (`frontend/agent-app`) now has its own login screen — an
    agent signs in with `agent_ref` + password (`POST
    /agents/{agent_ref}/login` on the ledger simulator, bcrypt-hashed,
    `AgentSession` DB-row-as-token, same style as the existing
    `OtpChallenge` pattern, no JWT library needed here). The resulting
    token is sent as `X-Agent-Token` on every subsequent lookup/OTP/transact
    call; `require_agent_session` (`app/security.py`) rejects a missing,
    expired, or **cross-agent** token (Ravi Kumar's token 403s on Priya
    Sharma's URL) before any beneficiary data is touched. This is a
    separate credential from the beneficiary's own OTP dual-factor and
    from the console's JWT login — three distinct auth boundaries in this
    codebase now, each proven live: console JWT, agent session token,
    beneficiary OTP.
  - **USSD PIN brute-force lockout:** `wallets.failed_pin_attempts` /
    `pin_locked_until` — 3 wrong PINs (`ussd_pin_max_attempts`) locks the
    beneficiary out for 15 minutes (`ussd_pin_lockout_minutes`), reset on
    the next correct PIN. Existing demo agents (AGT-001/002/003) were
    migrated with a default password (`ChangeMe123!`, same as the console
    demo logins) via a one-off DB update — see git history / ask before
    reusing that pattern for anything beyond local demo data.
  - **Bug found and fixed while building this:** every expiry check in
    `erupee-ledger-simulator` (`OtpChallenge.expires_at`, `UssdSession.
    expires_at`, and the new `AgentSession.expires_at` / `Wallet.
    pin_locked_until`) used to do `.replace(tzinfo=timezone.utc)` on a
    datetime read back from Postgres. That's only correct if the value is
    naive — but this deployment's Postgres session `TimeZone` is
    `Asia/Calcutta`, so psycopg always returns an IST-aware datetime, and
    `.replace(...)` relabels it as UTC instead of converting, silently
    inflating every TTL by 5.5 hours (a 15-minute PIN lockout measured as
    345 minutes in testing). Fixed via `app/timeutil.py`'s `as_utc()`
    helper, used everywhere a DB-sourced datetime is compared against
    `datetime.now(timezone.utc)`. Worth checking for the same pattern
    before adding any new expiry/TTL logic to this service.

## Services

| Service | Port | What it is |
|---|---|---|
| `services/erupee-ledger-simulator` | 8401 | Simulated sponsor bank e₹ ledger — wallets, issuance, redemption, programmable rule enforcement, agent-assisted dual-factor auth, USSD session state machine, offline queue sync |
| `services/sovereignx-core` | 8402 | Subsidy & DBT orchestration, beneficiary/consent, disbursement, reconciliation, compliance |
| `frontend/sovereignx-console` | 5401 | Scheme Administrator Console (React, Mandate360-theme) — Dashboard, Schemes, Agents, Compliance |
| `frontend/wallet-sdk-demo` | 5402 | Demo bank app embedding the wallet SDK (incl. offline queue UI), themed differently, proving white-labeling works |
| `frontend/agent-app` | 5403 | Banking Correspondent / CSC field app — dual-factor assisted withdrawal/redemption |
| `frontend/ussd-simulator` | 5404 | Feature-phone USSD session simulator (*99#-style menu) |
| `sdk/wallet-sdk` | — | `@finverge/sovereignx-wallet-sdk` — embeddable wallet components + offline queue client |

## Running everything locally

### Option A — Docker Compose (fastest way to see the whole system)

```bash
docker compose up --build
```

Brings up all 7 containers (Postgres + both backends + all 4 frontends) on
the same ports as manual dev servers (8401, 8402, 5401–5404) — nothing else
to install. A fresh environment is **not empty**: `erupee-ledger-simulator`
seeds a demo wallet (`BEN-CORE-001`), two merchants (`MER-001` grocery,
`MER-002` fertilizer — the latter demonstrates the programmable-rule block),
and the three demo agents (`AGT-001/002/003`, password `ChangeMe123!`) on
first startup, same idempotent pattern `sovereignx-core` already used for
its own demo console logins (`app/seed.py`).

Notes:
- Postgres is **not** published to a host port — this machine already runs
  a native Postgres on `localhost:5432` (see the `local-postgres-instance`
  project memory); the two backend containers reach the containerized one
  internally as `postgres:5432`. Add `"55432:5432"` under that service in
  `docker-compose.yml` if you want a host client against it directly.
- Frontend containers are static production builds (`vite build` → nginx) —
  **no hot-reload**. For active frontend development, use Option B below;
  reach for Compose when you just want the whole system running, or when
  demoing/handing it to someone else.
- Credentials, ports, and the seeded demo data are all dev-grade defaults
  hardcoded in `docker-compose.yml` and `app/seed.py` — same posture as
  everywhere else in this codebase (no secrets manager, no prod/staging
  split; see "What's real vs. simulated" above).
- `docker compose down -v` also drops the `pgdata` volume — the next
  `up --build` starts from a genuinely empty (then reseeded) database.

**Real bugs this build surfaced** (fixed, not just worked around): every
frontend's `npm run build` had never actually been run before — `npm run
dev` only exercises Vite's own dev-mode resolver, never `tsc -b`, so these
sat undetected until Docker's production build path hit them:
- `wallet-sdk-demo` imports `sdk/wallet-sdk/src` via a Vite-only alias with
  no matching TypeScript `paths` entry, and that SDK directory had no
  `node_modules` of its own — `tsc` couldn't resolve `react` for any file
  under it. Fixed with a `paths` mapping in `tsconfig.app.json` and a
  `sdk/wallet-sdk/package.json` devDependency on `react`/`@types/react`
  (installed in its own Dockerfile build stage too, not just on the host —
  `.dockerignore` strips `node_modules` from the build context).
- Two `constructor(private x: string) {}` parameter-properties (`sdk/
  wallet-sdk/src/client.ts`, `offlineQueue.ts`) violated `erasableSyntaxOnly`
  — expanded to a plain field + assignment.
- `sovereignx-console` is pinned to TypeScript ~5.7.2, which doesn't
  support the `erasableSyntaxOnly` compiler option (added in 5.8) that was
  set in its `tsconfig.app.json`/`tsconfig.node.json` anyway — removed.

If you add a new cross-package import (another `@sdk`-style alias, another
`../../shared` reach) or bump a frontend's TypeScript version, run `npm run
build` locally before assuming it works — `npm run dev` won't catch it.

### Option B — manual dev servers (hot-reload, for active development)

```bash
# 1. Ledger simulator
cd services/erupee-ledger-simulator
python -m venv venv && ./venv/Scripts/pip install -r requirements.txt
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8401

# 2. Core orchestration service (needs #1 running for disbursement/reconciliation)
cd services/sovereignx-core
python -m venv venv && ./venv/Scripts/pip install -r requirements.txt
./venv/Scripts/python -m uvicorn app.main:app --reload --port 8402

# 3. Admin console
cd frontend/sovereignx-console
npm install && npm run dev   # http://localhost:5401

# 4. Wallet SDK demo (optional — needs #1 running)
cd frontend/wallet-sdk-demo
npm install && npm run dev   # http://localhost:5402

# 5. Agent App (optional — needs #1 running)
cd frontend/agent-app
npm install && npm run dev   # http://localhost:5403

# 6. USSD Simulator (optional — needs #1 running)
cd frontend/ussd-simulator
npm install && npm run dev   # http://localhost:5404
```

Both Postgres databases (`erupee_ledger_simulator`, `sovereignx_core`) are
created on the shared local Postgres instance (`localhost:5432`,
`postgres`/`postgres`) — see `local-postgres-instance` project memory.

Demo console logins (password `ChangeMe123!` for all): `admin@sovereignx.dev`
(platform admin), `scheme.admin@sovereignx.dev` (scheme administrator),
`compliance@sovereignx.dev` (compliance officer), `bank.ops@sovereignx.dev`
(sponsor bank operator).

## Running the tests

```bash
# Backends — pytest against a REAL Postgres test database (created
# automatically: erupee_ledger_simulator_test / sovereignx_core_test on
# the same local instance the dev servers use), not SQLite. This matters:
# a SQLite test DB would never have caught the IST-timezone TTL bug (see
# "Recently closed gaps" above) — SQLite has no server-side session
# timezone to get wrong in the first place.
cd services/erupee-ledger-simulator && ./venv/Scripts/python -m pytest   # 45 tests
cd services/sovereignx-core && ./venv/Scripts/python -m pytest          # 26 tests

# Frontends + SDK — Vitest + React Testing Library. Smoke-level, not
# exhaustive: proves each app renders, its critical form/button states
# work, and it calls the right endpoint with the right payload — not
# full interaction coverage.
cd frontend/sovereignx-console && npm test   # 3 tests
cd frontend/wallet-sdk-demo && npm test      # 2 tests
cd frontend/agent-app && npm test            # 2 tests
cd frontend/ussd-simulator && npm test       # 2 tests
cd sdk/wallet-sdk && npm test                # 7 tests — offlineQueue's HMAC
                                              # signing logic, the client side
                                              # of the exact contract that had
                                              # the signature bug (see
                                              # "Verified end-to-end flow" below)
```

87 tests total. What each backend suite actually locks in (not just
happy-path CRUD): the programmable-rule engine (expiry/merchant-category/
single-use/insufficient-balance), agent session auth including the
cross-agent-token-must-403 case, the USSD PIN lockout **with a direct
regression test for the timezone bug** (asserts the lockout window lands
within ~2 minutes of the configured value, not 5.5 hours off), the offline
signature verification **with a direct regression test for the raw-string-
vs-reserialized-timestamp bug**, reconciliation's upsert-not-duplicate
behavior, and the Fraud360/AML360 velocity-anomaly rule. `services/
ledger_client.py` is tested with `respx` mocking the HTTP boundary, so
sovereignx-core's test suite never needs the ledger simulator running.

Test files import their target modules directly (`pythonpath = .` in each
`pytest.ini`) rather than needing the package installed — no extra setup
beyond the existing venv `pip install -r requirements.txt`.

## Verified end-to-end flow (live-tested, not just unit-level)

Login → create scheme → ingest beneficiary → grant consent → disburse
(real issuance call to the ledger simulator) → beneficiary redeems via
the Wallet SDK demo, including a **real-time blocked redemption** when the
merchant category doesn't match the scheme's programmable rule → run
reconciliation → compliance alert appears on the console's Compliance
page, exactly matching what the ledger actually did. Confirmed through
the browser, not just via curl.

- **Agent reconciliation (FSD FR-31):** Compliance → Run Reconciliation now
  pulls every onboarded agent's daily summary from the ledger simulator,
  same trigger as the redemption-event pull, and persists one row per
  (agent, day) — upserted in place if run again the same day, never
  duplicated. Visible on each Agent's detail page as a "Daily
  Reconciliation History" table, separate from the live on-demand totals
  above it.

Also live-verified, each through its own browser UI:

- **Agent-assisted:** agent looks up a masked balance → requests an OTP
  → beneficiary "reads" the simulated code → agent verifies it → the
  resulting session token gates a withdrawal/redemption, which still
  goes through the same programmable-rule engine (a fertilizer-locked
  scheme correctly *blocks* a cash withdrawal, since that's not
  "spending at a permitted merchant" — the agent-app UI shows the
  decline like any other rule failure, not a bug).
- **USSD:** dial → enter beneficiary ref → enter PIN → balance enquiry
  and merchant payment both work over the same short-lived, no-cache
  session state machine.
- **Agent App login + lockout:** sign in as AGT-001 (`ChangeMe123!`),
  look up a beneficiary, run the OTP dual-factor, complete a transaction —
  all gated by the session token end-to-end; sign out clears it. Separately,
  dialing in via the USSD Simulator and entering the wrong PIN three times
  live-locks the account with the correct "15 min" message (not the
  pre-fix "345 min").
- **Offline queue:** toggle "offline" in the Wallet SDK demo, queue a
  payment (HMAC-signed on-device), toggle back online, sync — the
  payment executes against the real ledger and the balance updates.
  Caught and fixed two real bugs getting here: a signature bug (the
  server re-serialized a parsed timestamp before verifying, producing a
  different string than the client signed) and a stale-state
  bug (the queue-status UI didn't know a sibling component had just
  queued a payment) — both now covered by `OFFLINE_QUEUE_CHANGED_EVENT`
  and a raw-string timestamp contract; see the code comments at each fix
  site before changing either again.

## Architecture note: the custody boundary

`sovereignx-core` never touches e₹ directly. Every balance-affecting call
goes through `erupee-ledger-simulator` over HTTP — the same shape as the
HLD's real e₹ Connector Adapter talking to a real sponsor bank. This is
the literal code expression of the BRD/FSD/HLD's central regulatory
thesis: Finverge orchestrates, it never custodies.
