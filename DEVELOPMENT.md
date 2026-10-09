# Development setup — Phase 6A checkpoint

The Next.js/TypeScript desktop workspace uses FastAPI/SQLite for mocked onboarding, sessions, profiles, contacts, inbox, persisted direct/group messages, authenticated WebSocket delivery, receipts, unread state, typing and real connection presence. Group creation, naming, membership administration, roles and leaving are implemented. Required settings categories are reachable Coming Soon placeholders; deployment remains deferred. The assignment PDF, REQUIREMENTS.md and DESIGN.md are preserved; their Phase 1 stop statements describe the earlier task. No requirement contradiction required correction.

## Prerequisites

Use Windows PowerShell, Python 3.13, and Node.js 24 with npm (the versions used for verification). Run commands in the stated directories. Commands use the virtual environment's Python directly, so changing PowerShell execution policy or activating the environment is unnecessary.

## Install and initialize

From a new PowerShell terminal:

```powershell
Set-Location F:\signal-clone\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
.\.venv\Scripts\python.exe -m app.init_db --seed
.\.venv\Scripts\python.exe -m app.init_db --seed
```

Use `requirements.txt` instead of `requirements-dev.txt` if tests are not needed. Runtime and development direct dependencies are pinned. `.venv/` is local and ignored.

Initialization runs `alembic upgrade head`. Repeating it does not drop or recreate tables. `--seed` inserts missing deterministic fixtures without overwriting existing rows, names, messages, receipts, or read cursors. Omit `--seed` for schema initialization alone. The fixture contains six fictional users, thirty directional contacts, four direct conversations, two groups, fifteen memberships, forty messages, and fifty-eight recipient receipts. Sessions/events start empty in a fresh seed; authentication and addressed realtime event workflows are implemented.

```powershell
Set-Location F:\signal-clone\frontend
if (-not (Test-Path -LiteralPath .env.local)) { Copy-Item -LiteralPath .env.example -Destination .env.local }
npm ci
```

Use `npm ci` to install the committed frontend lockfile. It was also run successfully as a clean-install check. Stop the frontend before reinstalling dependencies: Windows locks Next.js's native binary while the server is running. Use `npm install` only when intentionally changing dependencies.

## Run backend (terminal 1)

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend: `http://localhost:8000`. Health: `http://localhost:8000/health`. API documentation: `http://localhost:8000/docs`. Application startup does not run migrations or reset/seed the database. Health returns `{"status":"ok","database":"ok"}` when the DB is reachable and has an Alembic revision; otherwise it returns 503.

## Run frontend (terminal 2)

```powershell
Set-Location F:\signal-clone\frontend
npm run dev
```

Open `http://localhost:3000`. The page restores a session or displays mocked sign-in. Login as `alex` or `maya` using code `123456`, then choose a display name/avatar if prompted. The original connectivity page remains at `http://localhost:3000/health-check`. Client requests include credentials, validate JSON and time out after ten seconds. Stop each server with Ctrl+C.

## Configuration

| File/key | Default and behavior |
| --- | --- |
| backend/.env: APP_NAME | Signal Desktop Clone API |
| backend/.env: DATABASE_URL | sqlite:///./data/signal.db; relative paths resolve against backend/, even if the working directory differs |
| backend/.env: FRONTEND_ORIGIN | http://localhost:3000; a single exact HTTP(S) origin, no wildcard |
| backend/.env: SQLITE_BUSY_TIMEOUT_MS | 5000; validated positive timeout |
| backend/.env: MOCK_OTP | 123456; exactly six digits, openly displayed in the mock verification screen |
| backend/.env: SESSION_DAYS | 7; validated 1–30 day cookie/database lifetime |
| backend/.env: SESSION_COOKIE_SECURE | false for local HTTP; true when serving HTTPS |
| frontend/.env.local: NEXT_PUBLIC_API_URL | http://localhost:8000; API base URL without /api/v1 for the root health route |

Environment variables override backend `.env` values. Pydantic Settings loads the backend file by absolute path. Next.js embeds `NEXT_PUBLIC_*` values in frontend code: never put secrets there, and restart/rebuild after changing them. `localhost` and `127.0.0.1` are distinct CORS origins. If you change the frontend origin, update backend configuration to match. Restart the backend after configuration changes.

## Database model and invariants

| Table | Purpose |
| --- | --- |
| users | UUID identities, unique usernames/phones, normalized usernames, display name/avatar |
| sessions | User-linked SHA-256 opaque-token hashes, expiration and server-side logout revocation |
| contacts | Directional owner/contact composite identity; self-contacts rejected |
| conversations | Direct/group kind, creator, required group name, latest activity |
| direct_pairs | Canonically ordered user pair, unique across all direct conversations |
| conversation_members | Composite conversation/user identity, admin/member role, join/leave dates, unread cursor |
| messages | Monotonic sequence, UUID identity, conversation/sender, text/system kind, client send uniqueness |
| message_receipts | One receipt per message/recipient; delivery/read timestamps, read cannot precede delivery |
| user_settings | Per-user validated-at-API-boundary JSON settings storage; schema only |
| user_events | Monotonic per-recipient durable event history with bounded replay retention |
| group_creations | Immutable per-user creation request ID and fingerprint, linked uniquely to the group |

`alembic_version` records schema revisions, currently `0003` (additive group creation intent table; `0002` added persisted last-seen time). Foreign keys are enabled on every application connection, with WAL and a busy timeout. UUIDs are text; timestamp bindings require timezone-aware Python datetimes and store UTC, restoring UTC timezone information on reads. Named checks, unique constraints, and query indexes are committed in the migration. Contact-owner lookup uses the composite primary-key index. Parent deletion is restricted rather than silently cascading away message history.

The schema supports later workflows, but transaction/service code must still enforce direct-chat membership count, pair consistency, at least one group admin, sender/recipient eligibility, excluding sender receipts, monotonic read advancement, and settings-key validation. Group, message and receipt services enforce these multi-row eligibility/admin/cursor rules. Settings-key validation awaits its placeholder endpoints. Read cursor zero is a valid sentinel and is deliberately not a foreign key to messages. Recipient receipt rows represent send-time audience snapshots.

To add a future schema change, edit models then generate and review a migration; never substitute `create_all` for upgrading an existing database:

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m alembic revision --autogenerate -m describe_change
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m alembic check
```

## Run checks

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
Invoke-RestMethod -Uri http://localhost:8000/health
```

Inspect real SQLite tables and constraints (the server can remain running):

```powershell
Set-Location F:\signal-clone\backend
@'
from sqlalchemy import inspect, text
from app.database import engine
with engine.connect() as db:
    print(inspect(engine).get_table_names())
    print("foreign_keys:", db.scalar(text("PRAGMA foreign_keys")))
    print("foreign_key_check:", db.execute(text("PRAGMA foreign_key_check")).all())
    print("journal_mode:", db.scalar(text("PRAGMA journal_mode")))
'@ | .\.venv\Scripts\python.exe -
```

Frontend checks:

```powershell
Set-Location F:\signal-clone\frontend
npm run typecheck
npm run lint
npm run build
```

For production-mode local verification, stop the development frontend, then:

```powershell
Set-Location F:\signal-clone\frontend
npm start
```

With both servers running, in another terminal:

```powershell
Set-Location F:\signal-clone\frontend
npm run verify:connectivity
```

This command executes the exact frontend API utility against FastAPI, requests the frontend page, verifies allowed-origin credentialed CORS and preflight, and checks that unrelated-origin preflight is rejected. It uses Node HTTP, which does not enforce browser CORS. If using a custom local frontend address, set `$env:FRONTEND_ORIGIN` for this verification command. Separately open the page in a browser to confirm browser rendering/fetch and the visible states.

## Verification record and limits

Actual completed checks:

- Database initialization with `--seed` succeeded twice. Counts remained six users, six conversations, and forty messages. The tests also reran the seed after editing names, message text, and read state, and confirmed edits were preserved.
- Live Uvicorn startup succeeded; `GET /health` returned 200 with `status=ok` and `database=ok`.
- SQLite inspection confirmed all ten application tables plus `alembic_version`, `foreign_keys=1`, WAL, and an empty `foreign_key_check` result.
- Thirteen backend tests passed without warnings. `alembic check` reported no new upgrade operations.
- Frontend TypeScript checking, ESLint, and production build succeeded; the final lint run had no warnings.
- The type-check command generates Next.js route types first, so it also works before the first build on a fresh checkout.
- Production frontend startup succeeded. The actual typed frontend API utility reached the backend; the page served HTTP 200. Live CORS response headers and preflight permitted the configured credentialed origin, and unrelated-origin preflight returned 400 without an allow-origin header.
- Production-only dependency audit (`npm audit --omit=dev`) found zero vulnerabilities.

The initial sandbox build failed to spawn workers (`EPERM`); the final production build succeeded outside the sandbox. Browser automation was attempted with the installed Browser skill; discovery returned no available browser, so browser rendering, visible loading/error/success states, and browser-enforced fetch remain unverified. HTTP-level connectivity and CORS passed; they are not substitutes for browser UI verification.

Dependency audit: npm currently reports five high-severity entries along the development-only `eslint-config-next > @next/eslint-plugin-next > fast-glob > micromatch > braces` chain, stemming from [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). The available braces release is 3.0.3 and still falls in the affected range. npm suggests downgrading the Next lint config to 14.2.35; that is not a compatible foundation fix for the selected Next.js 16 stack. No forced downgrade or unverified override was applied. This is a tooling dependency limitation, not a failure of the local health endpoint. Recheck when a patched version is available.

ESLint is pinned within major 9 because the current Next lint plugins declare support through major 9. npm warns that this ESLint release is deprecated. Major 10 ran the checks but caused unsupported peer combinations, so it was not retained in the reproducible lockfile.

Reference documentation used for foundation choices: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [SQLAlchemy SQLite foreign keys](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#foreign-key-support), and [FastAPI CORS](https://fastapi.tiangolo.com/tutorial/cors/).

## Phase 3A visual checkpoint (historical; superseded below)

The root page now renders the actual component-based desktop workspace. The original Phase 2 connectivity page is preserved at `/health-check`; its health utility and FastAPI/SQLite foundation are unchanged. `npm run verify:connectivity` now checks the workspace at `/` and the foundation page at `/health-check`.

Visual baseline: the official Signal brand archive's `Chat.png` and `Group_Chat.png`, reopened before implementation. Both use the same rail-based desktop layout; the light Group_Chat theme is applied throughout, with blue direct-chat bubbles and the reference's red Family chat color. The archive supplies no release number. Operating-system controls, outer marketing texture, attachments, audio players, and reactions are excluded. Stock local avatar photos stand in for the reference's user photos; their download URLs are recorded in `frontend/public/avatars/SOURCES.md`.

Shared geometry/colors/type tokens live in `frontend/src/styles/tokens.css`. Reusable rail, sidebar/rows, pane/header, bubbles, receipts, and composer live in `frontend/src/components/messaging/`. SVG icons, avatar, and icon-button primitives live in `frontend/src/components/ui/`; no icon dependency or dependency upgrade was introduced.

Temporary data lives only in the typed `frontend/src/features/messaging/fixtures.ts`. The workspace accepts presentation models as props, ready for a later API adapter. Local case-insensitive sidebar search matches names and previews; selecting a row changes the open direct/group thread. Clicking the selected Chats rail icon clears the conversation and exposes the empty state. Unread numbers, timestamps, and receipt states are fixed fixture values; selection does not mark messages read or persist state. Reload restores the default Maya conversation.

New-chat, menu, settings, call, story, and composer action icons are intentionally inactive. The composer is read-only. No onboarding, sending, feature API, WebSocket, group-admin or settings workflow is added. The main page makes no backend requests in this checkpoint.

Layout uses 72px rail, 340px sidebar, a flexible `minmax(0, 1fr)` conversation pane, a 76px header, and a 72px composer. The sidebar and message history have independent scroll containers; the outer workspace fills `100dvh` and constrains horizontal overflow. The CSS targets desktop 1366×768 and 1920×1080; rendered verification at those sizes remains pending because browser discovery returned no available browser. The empty-state layout is provisional because neither official reference includes that state.

Phase 3A checks completed: frontend type checking, lint with no warnings, and production build all passed. The rebuilt production frontend was restarted at `http://localhost:3000`; the existing backend was not restarted. The workspace, preserved `/health-check` page, and all eight local avatar assets returned HTTP 200. The existing typed-API connectivity and allowed/rejected CORS checks passed. Browser interaction and screenshot comparisons remain pending. The frontend is left running for visual review; Phase 3B has not begun.

## Phase 3B: mocked onboarding and persisted queries (historical; superseded below)

No dependencies or database schema changed. Run the same initialization command to upgrade safely; existing seed data, profiles, contacts, conversations and messages are retained. A current `.env` without the three new authentication keys uses their defaults, so copying over an existing configuration is unnecessary.

The server validates usernames (3–50 characters, starting with a letter) or international phone numbers (`+` and 8–15 digits). The displayed fixed OTP deliberately mocks identity verification: no SMS, pairing or encryption occurs. It is public demo authentication, so anyone with the fixed code can access a demo identity. New identifiers create users and settings in SQLite. Profiles require a trimmed display name and a built-in avatar choice. Seeded users without an avatar complete this profile step once; a persisted avatar indicates completion and restores the correct screen after refresh.

Authentication uses an opaque random token in the `signal_session` HttpOnly, SameSite=Lax cookie. Only its SHA-256 hash is stored in SQLite. Every protected request checks expiration/revocation and loads the acting user on the server. Logout revokes that session and clears its cookie. Browser JavaScript does not store authentication tokens. Keep the frontend and API on `localhost` during this checkpoint, using the exact URLs below; do not mix `localhost` and `127.0.0.1`. Future hosting must use a compatible same-site cookie configuration or proxy and HTTPS; deployment is deferred.

Click the profile avatar at the rail's bottom to edit the profile or log out. Its dialog uses native modal focus handling and Escape dismissal. Contacts are directional and searched on the backend. New chat opens the contact picker; Add a contact searches registered users and supports an optional owner-only alias. Selecting a contact opens/creates a unique canonical direct pair. Repeated or concurrent creation requests return the same conversation. The assignment requires adding contacts, not an edit-contact workflow.

The inbox is restricted to active memberships and sorted by persisted activity with an ID tie-breaker. The checkpoint returns the complete small inbox; large-inbox cursor pagination is deferred. Existing local sidebar search operates on that real API result. History is cursor-paginated on the server and read through all pages by the typed adapter, then rendered chronologically. Alignment derives from current user ID; group names/senders, receipt aggregation and unread counts derive from database rows. Opening a chat does not mark it read: read acknowledgment and live updates belong to a later phase. A chosen conversation is preserved in the page URL. Empty threads render explicitly.

`frontend/src/features/messaging/fixtures.ts` remains isolated for the prior visual checkpoint and is not imported by the normal application. A failed API request produces an error with retry, never demo-data substitution. History requests are canceled/guarded when selection changes; stale inbox responses cannot overwrite a newly created chat. The main header/thread/composer geometry and design tokens are preserved. Presence is explicitly labeled as a demo value. Composer text and action controls remain disabled. There are no send or WebSocket endpoints.

Implemented `/api/v1` routes:

- `POST /auth/challenges`, `POST /auth/verify`, `GET /auth/session`, `POST /auth/logout`.
- `GET /me`, `PATCH /me`.
- `GET /users?query=`, `GET /contacts?query=`, `POST /contacts`.
- `GET /conversations?query=&filter=all|unread`, `POST /conversations/direct`.
- `GET /conversations/{id}`, `GET /conversations/{id}/messages?before_sequence=&limit=`.

Non-members receive 403 for existing conversation/history access; unknown conversations receive 404. Authentication, validation, conflicts and database errors use `{code, message, field_errors?}`. Origin validation rejects requests carrying an unconfigured origin; CORS allows only the configured frontend origin with credentials. `/health` remains available separately.

Additional live checks, with both servers running:

```powershell
Set-Location F:\signal-clone\frontend
npm run verify:connectivity
npm run verify:phase3b
```

The Phase 3B adapter check uses independent Node-managed cookies to exercise the actual typed client against Alex/Maya's live API sessions, stored history, same-ID direct reopening, unauthorized history and logout. It injects 503/network failures to verify that the client rejects them with useful errors rather than returning data. It does not change seed profiles or messages; generated verification sessions are revoked afterwards. These are HTTP/adapter checks, not browser UI verification.

Phase 3B verification: 18 backend tests passed using temporary SQLite databases, including registration by username/phone, validation, profile persistence, session restore/expiry/revocation, directional contacts/search/add/conflicts, user-specific inbox, direct/group paginated history, unread/receipt aggregation, unauthorized history, empty threads and eight concurrent direct-create requests producing one conversation. Alembic reports no new upgrade operations. Frontend type checking, lint and final production build passed (a restricted worker-spawn EPERM was resolved by rerunning the build outside the sandbox). Live typed-adapter, application HTTP, preserved health page and allowed/rejected credentialed CORS checks passed. The actual database retains six users, thirty contacts, six conversations, forty messages and fifty-eight receipts, with zero foreign-key violations. Browser discovery returned no available browser; browser interaction, refresh behavior, visible failure/retry and visual inspection remain pending manual review.

### Manual review in a normal browser and an incognito window

1. Open `http://localhost:3000` normally. Sign in as **alex**, Continue, then use **123456**. Save a profile/avatar if prompted. In an incognito window, repeat as **maya**. Each window should keep its own user and inbox after refresh.
2. Open direct and group rows, then switch quickly between them. Verify header and messages always belong to the selected chat, incoming/outgoing alignment, sender names, date separators, timestamps and stored receipt icons. Alex sees Roommates and Weekend plans; Maya sees Roommates but not Weekend plans. No message can be sent.
3. Use sidebar search. Click New chat, search for Maya in Alex's contacts, open her chat twice and confirm the conversation ID in the URL stays the same. Refresh and confirm the chosen conversation reopens. Use the Chats rail icon to check the empty selection.
4. In incognito, log out via the bottom profile avatar. Register a fresh username such as `review3b`, verify with **123456**, and save a profile. Its inbox/contacts should be empty. New chat → Add a contact → search `alex` → Add (optionally set an alias). Select Alex: an empty direct chat opens. Reopen it and refresh; it remains one conversation. Refresh Alex's normal window to see this persisted conversation.
5. For a direct authorization check, copy Alex's Weekend plans conversation ID from the URL. While signed in as Maya in incognito, run in that window's DevTools console (replace the ID): `fetch('http://localhost:8000/api/v1/conversations/PASTE_ID/messages', {credentials:'include'}).then(async r => console.log(r.status, await r.json()))`. Expect **403**, with no message history.
6. Use DevTools Network request blocking for `*localhost:8000/*`, then reload the app. Expect a connection error, with no demo inbox. Remove the blocking rule and press Retry. Alternatively stop/restart only the backend using the documented commands. Also block a history request while switching chats to review its inline retry state.
7. Edit the profile, refresh and verify it persists. Log out, refresh and verify sign-in returns. Sign in again to verify the saved profile is retained.

Review URLs: frontend `http://localhost:3000`; backend `http://localhost:8000`; health `http://localhost:8000/health`; API docs `http://localhost:8000/docs`. Both project servers are left available after the final production build. Phase 3B stops here for review; realtime messaging has not begun.

## Phase 4: real-time direct and existing-group messaging

The existing database is upgraded in place by migration `0002`, which adds nullable `users.last_seen_at`. No tables or seeded rows are reset. Run initialization before starting the updated backend:

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

**Exactly one backend worker/instance is required.** The connection registry and ephemeral typing state live in that process. SQLite stores messages, recipient receipts, read cursors, sessions, last-seen timestamps and addressed recovery events. Multiple workers require a shared fan-out service, which is outside this checkpoint. Short synchronous SQLite operations run in the asynchronous mutation/socket handlers to preserve local commit/event order; this setup targets the small assignment dataset, not large-scale chat traffic. Developer `--reload` is still usable with its single serving process; reload disconnects clients and they recover automatically.

No dependencies were upgraded. The installed `uvicorn[standard]` already includes the WebSocket implementation used by protocol tests. The frontend defaults to deriving `/api/v1/ws` from `NEXT_PUBLIC_API_URL`, converting HTTP to WS and HTTPS to WSS. Optionally set the full endpoint `NEXT_PUBLIC_WS_URL` (documented in `.env.example`). Rebuild the production frontend after changing either public URL. Cookie/Origin constraints from onboarding still apply; same-origin reverse-proxy hosting remains the planned deployment architecture.

Sending accepts 1–4000 non-whitespace characters and a UUID `client_message_id`. The server derives the sender from the cookie session and checks active conversation membership. It creates the message, send-time recipient receipt snapshot, conversation activity, and per-user recovery events in one transaction. Only after commit does it confirm/send events. Repeating the same sender/client ID and content returns the original message; reusing that ID with a different conversation/body returns 409. Text is rendered as text, including Shift+Enter newlines.

The composer supports Enter (except while IME composition is active), Shift+Enter and a send button. The outgoing bubble shows a clock while pending, receipt checks after persistence, or `Failed · Retry` with the failure in a tooltip. Retrying uses the original ID. Server responses and socket events reconcile the same optimistic send by ID. Unsent per-conversation drafts and unconfirmed sends are stored in this tab's user-scoped `sessionStorage`; after refresh, unconfirmed sends remain retryable until history confirms them. Drafts remain in memory if browser storage is blocked. Logout uses the server's existing revocation flow and closes connections associated with that session; the frontend also removes socket listeners/timers on unmount.

Server frames carry addressed `UserEvent.sequence` IDs, conversation snapshots and changed messages. The client deduplicates IDs/messages, sorts by message sequence, and merges receipts monotonically so an older HTTP history snapshot cannot downgrade a live receipt. Inbox snapshots are guarded against events arriving during a fetch. New direct-conversation creation sends a durable update to both participants, including a recipient whose inbox was empty. Messages update previews, activity, ordering and unread counts for chats that are not open. No interval polls inbox or history.

Receipt semantics:

- **Sent:** SQLite committed the message and its addressed recipient rows. Queuing a broadcast does not imply delivery.
- **Delivered:** an authenticated recipient client acknowledges receipt via WebSocket `message.delivered` or the equivalent HTTP endpoint. Recovery clients fetch their own pending-delivery IDs and those conversations' persisted message content before acknowledging them in batches; this also covers messages received while another chat is selected.
- **Read:** the rendered selected conversation is visible, its browser document has focus and the thread is at the bottom. The client submits its rendered through-sequence. The server validates the sequence belongs to that conversation, advances the member cursor monotonically and sets read/delivery timestamps only on messages addressed to that user. A blurred/hidden page does not mark a chat read. Own sends never increase unread counts. A persisted read update clears the sidebar badge; opening an inactive window alone cannot fake reading.
- For groups, the outgoing aggregate is **read only when every send-time recipient has read**, **delivered when every recipient has delivered**, otherwise sent. A read acknowledgement also satisfies delivery. New group members do not inherit old receipt obligations; Phase 5 membership workflows are documented below.

Typing is sent at most approximately once per 1.2 seconds while editing; the server also throttles updates to once per second. It stops on send, empty draft, blur, inactivity, conversation change or disconnect. The server and frontend expire stale indicators after five seconds. Presence derives from authenticated socket connections: a user is online while at least one connection exists, and the last connection's departure persists last-seen time. Contact/header labels no longer claim static demo presence. Profile name edits update active typing names.

Disconnects show a concise sidebar notice and reconnect with 1/2/4/8/15-second bounded backoff. Heartbeats detect broken connections; session revocation/expiry closes the socket. Reconnect requests user-scoped replay and always refetches authoritative inbox and active history/receipts, then acknowledges missed delivery. Event replay is limited to 200 frames; larger gaps use authoritative resynchronization. SQLite retains the most recent 1,000 recovery events per user; message history is not pruned. Slow-client output queues are bounded and close the connection for resync rather than retaining unlimited memory. Last-seen may be delayed until a broken transport is detected. There is no automatic retry of failed sends: retry is explicit and idempotent.

Header title/status now share a constrained flexible area with ellipsis; action icons cannot be squeezed over the text. Full desktop dimensions retain the original 72px rail/340px sidebar. At widths below 1000px, a 60px rail/260px sidebar and smaller header gaps keep two desktop windows usable. This is a targeted two-window adjustment, not a mobile redesign. The initial composer remains 72px high and expands for up to three visible draft lines.

Additional HTTP routes: `POST /api/v1/conversations/{id}/messages`, `POST .../{id}/delivered`, `POST .../{id}/read`, `GET /api/v1/messages/pending-delivery`. Socket endpoint: `/api/v1/ws?cursor=N`. Commands: `message.delivered`, `conversation.read`, `typing.started`, `typing.stopped`, `ping`. Server events: `session.ready`, `message.created`, `message.receipt_updated`, `conversation.updated`, `typing.updated`, `presence.updated`, `sync.required`, `pong`, `error`. Every history/send/ack/typing/replay checks the relevant membership/recipient; clients cannot acknowledge another user's receipt. WebSocket handshakes require the configured Origin and a valid cookie, and logout closes all sockets belonging to that session.

Verification commands:

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
Set-Location F:\signal-clone\frontend
npm run typecheck
npm run lint
npm run verify:messaging-state
npm run build
# Stop only the existing project frontend after a successful build, then:
npm start
# With both project servers running:
npm run verify:connectivity
npm run verify:phase3b
```

Verification completed: **19 backend tests passed**. The new protocol test launches real Uvicorn on a temporary port with an isolated SQLite database, connects five authenticated sockets (including a sender's second session), and exercises direct/group delivery, message persistence, six repeated same-ID sends yielding one row, invalid input and sender spoof rejection, non-member send/receive/ack rejection, delivered/read transitions, monotonic timestamps, unread clearing, typing expiry, new direct appearance, offline send/replay/resync without duplicates, multiple-connection presence, persisted last-seen and logout socket closure. Schema initialization twice and Alembic consistency checks passed. Frontend type checking, lint, state/contract checks and final production build passed. State checks specifically cover duplicate/out-of-order merging, non-regressing receipts, client IDs/alignment and HTTPS→WSS derivation. Browser access is unavailable; DOM interaction, visual comparison and browser-focused read behavior remain manual checks.

### Alex + Maya two-window manual review

1. Open `http://localhost:3000` normally as **alex** and in Incognito as **maya**. Continue → fixed code **123456** → save profile/avatar if prompted. New chat can open the existing Alex/Maya direct pair. Keep both windows side by side, and click the intended window to give it focus. Review at 1366×768 and 1920×1080, including half-width windows; names/status must truncate before the action icons.
2. In Maya's window, select Roommates (or another chat). In Alex's direct composer, type a few characters without sending: Maya's Alex chat should report typing if it is open, and the indicator should disappear after stopping for about five seconds or switching/sending. For this typing check, first keep Maya's Alex chat open; switch Maya to Roommates for the next unread check.
3. Send **Alex → Maya** with Enter while Maya is viewing Roommates. Maya's Alex row should move/update its preview and show unread. Alex should progress from the pending clock to sent, then delivered outline double checks after Maya's client acknowledges; it must not show read yet. Open Alex's chat in Maya's window and click/focus that window at the bottom: the badge clears and Alex's receipt fills to read.
4. Send **Maya → Alex** using the send button. Click/focus Alex's window to read it. Try Shift+Enter multiline text, whitespace-only text (cannot send) and rapid sends; both windows must retain chronological messages without duplicates. Click another chat while a reply arrives and verify its preview/unread update without refresh.
5. Refresh both windows. Sessions, messages, sender alignment and persisted receipts/unread should remain correct. Type an unsent draft, switch chats and return, then refresh: the draft should survive. Send to Roommates from either account; both members receive it. The group's aggregate receipt can remain sent/delivered until **kai** also signs in and acknowledges/reads; this is expected per-recipient behavior.
6. Close Maya's Incognito window entirely, send a message from Alex, and expect sent until Maya reconnects. Reopen Incognito and sign in as Maya: authoritative history restores the missed message once, then delivery/read advance appropriately. To test automatic same-session reconnect, restart only the project's backend while the browser windows stay open; both should show reconnecting and recover after the server returns. If the backend was started in your terminal, use Ctrl+C and rerun the one-worker command above. Otherwise identify the project Uvicorn PID with `Get-NetTCPConnection -LocalPort 8000 -State Listen` plus `Get-CimInstance Win32_Process`, stop only that confirmed PID, and run the documented backend command.
7. For failed-send retry, use DevTools Network request blocking for `*localhost:8000/api/v1/conversations/*/messages` in Alex's window and send a distinctive message. Expect `Failed · Retry`. Remove the rule, press Retry, and confirm exactly one matching message appears in both clients. Also try a backend outage while drafting/sending, restore it, and confirm reconnect preserves drafts/unconfirmed sends without replacing errors with fixtures.
8. Log out via the bottom profile avatar. Its socket should close; refreshing shows sign-in. The other user's session remains usable. Calls, stories, media actions, settings workflows and group creation/admin remain unavailable; they were not added in Phase 4.

Live handoff checks also passed: the restarted frontend and preserved health page return HTTP 200, the typed adapter reaches `/health`, configured credentialed CORS is accepted and another origin rejected, and the Phase 3B live adapter checks still pass with both populated and manually created empty conversations. The running project WebSocket was additionally checked for session authentication, heartbeat and logout closure (1008), without adding test messages to the real database. The migration retains the six existing users, eight conversations (including the manually created empty chats), forty messages and fifty-eight receipts, with no foreign-key violations. The full protocol suite uses its isolated database for message-writing scenarios, including explicit Alex→Maya and Maya→Alex exchange.

Historical Phase 4 handoff: both review servers were left running at `http://localhost:3000` and `http://localhost:8000`. The Phase 5 checkpoint below supersedes that stop boundary.

## Phase 5: group creation and administration

No dependencies changed. Upgrade the existing database before restarting the backend; do not delete it or rerun a destructive seed. Migration `0003` only adds `group_creations`. It records `(user_id, client_group_id)` as a composite primary key, the immutable creation fingerprint, and a unique group foreign key. The name may subsequently change without breaking a retry of the original creation request.

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pytest -q
# Run in the backend terminal after stopping its existing project server:
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Continue using **one backend worker**. Group mutations and realtime fan-out run as short, non-awaiting transactions on that worker; the database also enforces creation intent and membership uniqueness. The connection registry and typing audience are in memory. Multiple workers require a shared event broker and additional concurrent-admin transaction locking; they are not supported by this checkpoint.

```powershell
Set-Location F:\signal-clone\frontend
npm run typecheck
npm run lint
npm run verify:messaging-state
npm run build
# After a successful build, stop only the existing project frontend, then:
npm start
# With both servers running, in another terminal:
npm run verify:connectivity
npm run verify:phase3b
```

New chat now includes **New group**. Choose contacts, continue to a required 1–100 character trimmed name, then create. The creator is automatically an admin; select at least one other member, with at most 100 total members. Duplicate IDs, self-selection, unknown/non-contact users and invalid names are rejected. The UI disables repeated submission, freezes the attempted creation details on failure and retries with the original UUID. SQLite creation, membership rows and addressed inbox events commit atomically. Every active member receives `group.created`; the creator opens the group. There is no fixture fallback.

The group header's overflow button opens **Group details** in a native modal with Escape dismissal/focus containment. It shows the name, active roster and Admin labels. Admins can rename, add contacts, remove members and promote/demote admins. Members can leave. Removal, role changes and leaving have confirmations. Saving and failure states are explicit; stale UI permissions cannot override server membership/admin checks. Changing the group avatar, descriptions, invite links and advanced permissions are outside this phase. These form/modal layouts follow the existing shell and documented Signal flow; exact creation/details screenshot geometry remains unverified as recorded in DESIGN.md.

The last active admin cannot leave, be removed or be demoted: promote another active member first. This also applies to a one-person group; empty/archive/delete-group workflows are outside scope. Removed membership rows retain `left_at` instead of being deleted. Re-adding a departed user reactivates the same unique row as an ordinary member, records a fresh join time, and starts the read cursor at the current message sequence. The user can then view **full conversation history**, including pre-join messages, as proposed in DESIGN.md. They acquire receipts/unread obligations only for messages sent to them while active; receipt rows are never retroactively created or deleted. Receipt aggregation continues to use the original send-time recipients. Consequently an earlier message can remain sent/delivered if a recipient left before acknowledging it; membership removal does not fabricate their acknowledgement.

Group changes create centered system entries without recipient receipts or unread counts. Name/role/membership changes emit `group.members_updated` snapshots to active members. Removal/leaving also commits an addressed `conversation.access_revoked` event for the departed user. Existing socket connections lose that conversation's queued private frames and typing audience immediately; future fan-out excludes departed users. Commands and replay independently check current membership. The client removes the inaccessible row/pane/cache/draft/pending sends, closes its details modal and ignores late responses that would restore it. Other conversations' drafts and messaging remain intact. Added/re-added users receive an inbox event without refreshing; authoritative reconnect sync also removes inaccessible groups if replay is unavailable.

### Group REST contracts

All paths use `/api/v1`, existing HttpOnly cookie sessions and configured Origin checks. Errors retain the standard `code`, `message`, optional `field_errors` shape.

| Method/path | Body and response |
| --- | --- |
| POST /groups | `{client_group_id: UUID, title, member_ids: UUID[]}` → group details; identical retry returns original group; different payload with the same ID returns 409 |
| GET /groups/{id} | Active member only → `{conversation, members: [{user, role, joined_at}], my_role}` |
| GET /groups/{id}/members | Active member only → active roster |
| PATCH /groups/{id} | Admin only, `{title}` → group details |
| POST /groups/{id}/members | Admin only, `{member_ids}` from their contacts → group details; already-active member returns 409 |
| PATCH /groups/{id}/members/{user_id} | Admin only, `{role: "admin" or "member"}` → group details; last-admin demotion returns 409 |
| DELETE /groups/{id}/members/{user_id} | Admin only → group details; self-removal must use Leave group |
| POST /groups/{id}/leave | Active member only → `{ok: true}`; last admin returns 409 |

Removed users receive 403 for history, group details, sends, delivered/read acknowledgements and typing commands. Existing per-recipient receipts and earlier messages remain in SQLite. `group.created`/`group.members_updated` use the existing durable envelope and conversation/messages snapshot. `conversation.access_revoked` carries only `conversation_id`, including on eligible reconnect replay; it contains no private message data.

### Alex, Maya and Kai manual review

Use `http://localhost:3000/`. Backend health: `http://localhost:8000/health`; API docs: `http://localhost:8000/docs`. Sign in with exact identifiers **alex**, **maya**, **kai**, and the openly mocked verification code **123456**. Complete name/avatar selection if prompted. Use Alex in a normal window, Maya in Incognito, and Kai in a separate browser/profile. Two Incognito windows in one browser share cookies and do not create independent identities.

1. As Alex, New chat → New group → select Maya → Next → enter `Phase 5 review` → Create. Verify it opens for Alex and appears in Maya's inbox without refresh. Its header overflow opens the roster: Alex is Admin, Maya is Member. Refresh both and verify the same group/roles remain.
2. Send messages both ways, including Shift+Enter multiline text. Keep Maya on another chat for an unread badge, then open/focus the group at the bottom to clear it. Check typing, delivered/read receipts and refresh persistence. An open but blurred window does not mark messages read.
3. As Maya, group details must show no rename/add/remove/admin controls. Try Leave → Cancel first. As Alex, rename the group and add Kai. Kai's inbox gains it without refresh; Kai can read pre-join history and has no retroactive unread badge. Send a new message: its aggregate becomes read only after both Maya and Kai read it.
4. Type as Maya, then remove Maya from Alex's details and confirm. Maya's group row and active pane disappear; Kai's typing indicator clears. Send again as Alex/Kai: Maya must receive no future message/typing. Refresh Maya and verify the group remains absent. Alex/Maya direct messaging should still work.
5. Re-add Maya. Verify one membership entry, ordinary-member role, no historical unread obligation and realtime receipt of a new message. Maya can now leave with confirmation; the group disappears again. Earlier thread/system history remains for Alex/Kai.
6. Try Alex leaving or removing his own admin role while he is the only admin: expect an explicit last-admin error. Promote Kai, then Alex can leave. Kai remains Admin. Test refresh and continued messaging. A sole remaining admin cannot leave until another member is added/promoted.
7. Close a recipient's browser, send while offline, then reconnect/sign in; history should recover once. For automatic reconnect, stop/restart only the verified one-worker project backend using the commands above. Inspect at 1366×768 and 1920×1080, plus side-by-side windows: fixed header/composer, scrollable thread and truncating title/action spacing must remain intact. Logout one user and verify the other two still work.

### Phase 5 verification record

- **21 backend tests passed**. Real Uvicorn/WebSocket protocol tests use isolated temporary SQLite databases. The group lifecycle test covers five concurrent same-intent creations yielding one group, input validation, persisted creator/member roles, ordinary-member mutation rejection, add/remove/re-add/leave, last-admin protection, renaming and original creation retry after rename. Three authenticated clients verify new-group inbox events, full pre-join history without retroactive receipts/unread, group delivery/read aggregation, typing cleanup, removal through existing connections, forbidden send/history/ack/typing after removal, revocation replay, rejoined realtime delivery and existing direct messaging. A queue test verifies removal discards buffered private events and removes stale typing recipients.
- **Migration initialization twice passed** at revision `0003`; Alembic reported no new upgrade operations. Every pre-existing record was compared before/after and remained identical: six users, thirty contacts, eight conversations, nineteen memberships, fifty-seven messages, seventy-seven receipts, fifteen sessions, six settings and 163 user events. New `group_creations` was empty; foreign-key check returned no violations. Subsequent live adapter checks create/revoke test sessions and can add recovery events, so session/event counts naturally change.
- **Frontend type checking, ESLint, state/contract verification and production build passed**, including typed group update/revocation events, duplicate/out-of-order reconciliation and HTTPS→WSS derivation. The final production server runs the rebuilt access-revocation/reconnect code.
- **Live frontend and backend checks passed**: root page HTTP 200, `/health` reports both `ok`, typed API connectivity succeeds, configured credentialed CORS/preflight is accepted and unrelated-origin preflight rejected. Phase 3B session/contact/history/error handling regressions pass against the running project; no fixture substitution occurs on API/network failure.
- **Browser checks pending**: Browser setup/discovery found no connected browser. New group forms, dialog focus/confirmation interactions, visibility-based read behavior, two-window rendering and visual comparison need the manual checklist above. Protocol checks do not claim browser validation or hosted verification. No deployment was performed.

### Current mandatory coverage audit after Phase 6A

This supersedes the Phase 5 missing-item audit. Every mandatory item/category from REQUIREMENTS.md is accounted for below. Historical requirements checkboxes remain unchanged; the current implementation/evidence is this audit. New Phase 6A browser checks remain pending; Phase 5 groups were subsequently manually approved by the user. Publishing, hosting and submission remain unfinished.

| Requirement(s) | Implementation location | Verification / status |
| --- | --- | --- |
| Next.js + TypeScript | frontend/package.json; frontend/src/app; frontend/src/features/messaging/api.ts | Implemented; type checking, lint and production build pass. |
| FastAPI Python | backend/app/main.py; backend/requirements.txt | Implemented; HTTP/WebSocket regression suite passes. |
| SQLite / independent schema | backend/app/models.py; database.py; migrations/ | Implemented; FK/constraint/repeatable migration tests pass; existing data preserved. |
| WebSockets | backend/app/live_routes.py; realtime.py; frontend/src/features/messaging/use-messaging.ts | Implemented; direct/group/replay/logout protocol tests pass; prior manual approval. |
| Mock authentication/registration | backend/app/auth.py; schemas.py; frontend/src/components/messaging/onboarding.tsx | Implemented; tests/test_phase3b.py and prior manual approval cover persistence, validation, restoration and logout. |
| Phone or username registration | backend/app/auth.py; schemas.py; frontend/src/components/messaging/onboarding.tsx | Implemented; tests/test_phase3b.py and prior manual approval cover persistence, validation, restoration and logout. |
| Display name / profile avatar | backend/app/auth.py; schemas.py; frontend/src/components/messaging/onboarding.tsx | Implemented; tests/test_phase3b.py and prior manual approval cover persistence, validation, restoration and logout. |
| Login / logout / session reload persistence | backend/app/auth.py; schemas.py; frontend/src/components/messaging/onboarding.tsx | Implemented; tests/test_phase3b.py and prior manual approval cover persistence, validation, restoration and logout. |
| Left conversation list / open pane | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Recent-activity sorting | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Conversation and contact search | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Add new contact | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Unread indicators | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Last-message previews | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Online/last-seen indicators | backend/app/messaging.py; message_service.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-sidebar,contact-picker}.tsx | Implemented; Phase 3B/4 tests and prior manual review pass. Live data only; no fixture fallback. |
| Realtime two-user text send/receive | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Message timestamps | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Single/double-check delivery/read receipts | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Typing indicators | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Sending / sent / delivered / read states | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Persist every message | backend/app/message_service.py; live_routes.py; frontend/src/features/messaging/use-messaging.ts; components/messaging/{conversation-pane,receipt}.tsx | Implemented; tests/test_realtime.py covers protocol/persistence/dedup/receipts/typing/reconnect; Phase 4 manually approved. |
| Create named group with members | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| Send / receive group messages | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| View group members | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| Admin add members | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| Admin remove members | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| Persist all group data/messages | backend/app/groups.py; models.py; frontend/src/components/messaging/{new-group,group-details}.tsx | Implemented; tests/test_groups.py covers lifecycle/admin/revocation; Phase 5 manually approved by user. |
| Closely reproduce Signal design/UX/navigation/look | DESIGN.md; frontend/src/styles/tokens.css; components/messaging/workspace.module.css; navigation-rail.tsx; conversation-pane.tsx | Reviewed messaging layout preserved. New Phase 6A menus/settings/toasts require manual browser review; exact unseen screenshots remain unverified. |
| Study Signal UI | DESIGN.md reference evidence; official Chat.png and Group_Chat.png | Completed before visual implementation; official rail-based desktop baseline, no release number supplied. |
| Conversation-list/chat-pane navigation/layout | DESIGN.md; frontend/src/styles/tokens.css; components/messaging/workspace.module.css; navigation-rail.tsx; conversation-pane.tsx | Reviewed messaging layout preserved. New Phase 6A menus/settings/toasts require manual browser review; exact unseen screenshots remain unverified. |
| Bubbles / threading / message grouping | DESIGN.md; frontend/src/styles/tokens.css; components/messaging/workspace.module.css; navigation-rail.tsx; conversation-pane.tsx | Reviewed messaging layout preserved. New Phase 6A menus/settings/toasts require manual browser review; exact unseen screenshots remain unverified. |
| Forms / modals / search / filters | frontend/src/components/ui/action-menu.tsx; components/messaging/{conversation-sidebar,settings-dialog}.tsx; features/messaging/notifications.ts | Implemented All/Unread on real inbox state; policy checks pass; search/form/group flows previously approved. New menu/filter browser checks pending. |
| Notifications/toasts | frontend/src/components/ui/toasts.tsx; features/messaging/{notifications,use-messaging}.ts; group/contact/profile components | Implemented incoming and operation feedback; policy tests cover dedup, self/system/replay and active-reading suppression. No permission request; browser checks pending. |
| Privacy settings placeholders | frontend/src/components/messaging/settings-dialog.tsx; navigation-rail.tsx; signal-workspace.tsx | Implemented reachable Coming Soon category; light theme unchanged, no fake preference controls. Native modal/navigation type/build checks pass; browser interaction pending. |
| Notification settings placeholders | frontend/src/components/messaging/settings-dialog.tsx; navigation-rail.tsx; signal-workspace.tsx | Implemented reachable Coming Soon category; light theme unchanged, no fake preference controls. Native modal/navigation type/build checks pass; browser interaction pending. |
| Appearance settings placeholders | frontend/src/components/messaging/settings-dialog.tsx; navigation-rail.tsx; signal-workspace.tsx | Implemented reachable Coming Soon category; light theme unchanged, no fake preference controls. Native modal/navigation type/build checks pass; browser interaction pending. |
| Seed SQLite immediately usable | backend/app/seed.py; init_db.py; migrations/; tests/test_foundation.py | Implemented; six users, multiple direct/groups, forty seeded messages; repeatable seed preserves user edits. |
| Seed multiple users | backend/app/seed.py; init_db.py; migrations/; tests/test_foundation.py | Implemented; six users, multiple direct/groups, forty seeded messages; repeatable seed preserves user edits. |
| Seed multiple conversations | backend/app/seed.py; init_db.py; migrations/; tests/test_foundation.py | Implemented; six users, multiple direct/groups, forty seeded messages; repeatable seed preserves user edits. |
| Seed multiple messages | backend/app/seed.py; init_db.py; migrations/; tests/test_foundation.py | Implemented; six users, multiple direct/groups, forty seeded messages; repeatable seed preserves user edits. |
| README setup instructions | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| README actual technology stack | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| README architecture overview | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| README database schema | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| README API overview | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| README assumptions/mocks/omitted bonuses | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| Original source / no plagiarism | frontend/ and backend/ source; PDF and reference attribution in DESIGN.md | Independently implemented; no Signal clone repository copied. |
| Public GitHub repository | README.md deployment preparation; backend/app/serve.py; .env.production.example files | PENDING outside Phase 6A: provider/account/storage/origin selection, public repository/publishing, hosted tests and submission links. No links invented. |
| Repository frontend/ and backend/ | frontend/; backend/; root .gitignore | Local structure present. Public remote repository not created or pushed in Phase 6A. |
| Required README delivered | README.md (local setup, stack, environment, schema/API, architecture, mocks, tests, deployment preparation sections) | Completed local documentation artifact. Provider-specific instructions and verified hosted URLs await provider selection/publishing. |
| Cloud deployment working app | README.md deployment preparation; backend/app/serve.py; .env.production.example files | PENDING outside Phase 6A: provider/account/storage/origin selection, public repository/publishing, hosted tests and submission links. No links invented. |
| Hosted working demo link | README.md deployment preparation; backend/app/serve.py; .env.production.example files | PENDING outside Phase 6A: provider/account/storage/origin selection, public repository/publishing, hosted tests and submission links. No links invented. |
| Submit public GitHub repository link | README.md deployment preparation; backend/app/serve.py; .env.production.example files | PENDING outside Phase 6A: provider/account/storage/origin selection, public repository/publishing, hosted tests and submission links. No links invented. |
| Submit deployed app link | README.md deployment preparation; backend/app/serve.py; .env.production.example files | PENDING outside Phase 6A: provider/account/storage/origin selection, public repository/publishing, hosted tests and submission links. No links invented. |
| Functionality evaluation: all core features | backend/tests/; frontend/scripts/; DEVELOPMENT.md phase verification | All mandatory local feature implementations present with permitted placeholders. Phase 6A browser review and hosted end-to-end verification remain; entire assignment is not complete. |
| UI/UX evaluation: similarity/original UX | DESIGN.md; frontend/src/styles/tokens.css; components/messaging/workspace.module.css; navigation-rail.tsx; conversation-pane.tsx | Reviewed messaging layout preserved. New Phase 6A menus/settings/toasts require manual browser review; exact unseen screenshots remain unverified. |
| Database design / relationships | backend/app/models.py; migrations/; tests/test_foundation.py | Implemented/tested; indexes, FKs, uniqueness, historical memberships and recipient snapshots. |
| Backend/API design | backend/app/{auth,messaging,message_service,groups,live_routes,schemas,main}.py | Implemented/tested; session/member/admin permissions, validation, consistent errors and commit-before-broadcast. |
| Code quality / readability / organization | backend service/router/model separation; typed frontend adapters; reusable components/ui/ | Modular implementation with type/lint/build checks; final review still needed. |
| Modularity / separation / reuse | backend service/router/model separation; typed frontend adapters; reusable components/ui/ | Modular implementation with type/lint/build checks; final review still needed. |
| Code understanding / explain submitted lines | README.md architecture/schema/API; DESIGN.md; DEVELOPMENT.md | Documentation prepared; user code walkthrough/evaluation remains (not claimed automatically verified). |
| User deadline 9 October 6pm IST | REQUIREMENTS.md, DESIGN.md, DEVELOPMENT.md | Unchanged deadline; hosting/repository/hosted tests still need a later authorized phase. |
| PDF approximate 24h effort not extra time | REQUIREMENTS.md, DESIGN.md, DEVELOPMENT.md | Respected; bonuses deferred, focused Phase 6A only. |
| Phase 1 documents before implementation | REQUIREMENTS.md, DESIGN.md, DEVELOPMENT.md | Completed before scaffolding. Historical Phase 1 stop rules were followed; later implementation expressly authorized. |

Permitted mocks/placeholders: fixed OTP, plaintext/no real Signal encryption, Privacy/Notifications/Appearance Coming Soon, Calls/Stories/Linked devices Coming Soon. These destinations are now reachable; no fake settings state or OS notification permission is introduced. The proposed `/me/settings` preference APIs are unnecessary for honest category placeholders and remain deferred. In-chat message search is not a PDF must-have; its icon remains unavailable. Contact editing is not separately mandated by the PDF; contact adding/aliasing works.

Optional bonuses remain deferred: attachments, reactions, reply/quoted messages, disappearing messages, dark mode, broader mobile/tablet layouts and additional shortcuts. Required composer Enter/Shift+Enter and reviewed desktop/two-window sizing remain implemented.

## Phase 6A implementation and deployment preparation

All/Unread filter chips and Chats menu filter actions use the current backend-derived inbox and stored unread counts. Search combines with the selected filter; reading can remove a row from Unread without closing the active pane. Main menu routes to Chats/New chat/New group/Settings/Linked devices/Profile and logout. Conversation menus expose group or direct contact details. Calls/Stories and all three required settings categories display explicit Coming Soon surfaces. Native dialogs handle focus/Escape; menus support button keyboard focus, outside dismissal and Escape. Exact new-screen geometry remains provisional as documented in DESIGN.md.

In-app toasts cover incoming messages, contact/group creation, group changes, profile saving and logout; validation/failures retain useful inline errors and retries. Incoming notifications are message-ID deduplicated and suppress own/system events, reconnect replay and a conversation actively being read. Reading requires focus/visibility/bottom/loaded history and no obscuring picker/modal. Reconnect catch-up is quiet; unread/history remain authoritative. Toasts are bounded to four, dismissible, expire after 6.5 seconds and can open their accessible conversation. Old toast actions cannot reopen revoked groups; logout clears previous-user notifications. No OS permission is requested. Group save success also appears inside its modal because native modal top-layer content covers document-level toasts.

Production configuration examples are in backend/.env.production.example and frontend/.env.production.example; their example.invalid origins are deliberately non-working. `WEBSOCKET_ORIGIN` is an optional exact HTTP(S) browser origin distinct from the WS endpoint, defaulting to FRONTEND_ORIGIN. `PORT` is validated. `.python-version` and `.node-version` document Python 3.13/Node 24; npm manifests declare Node >=24 <25. Dependency versions are unchanged. Root .gitignore excludes environment secrets, SQLite/WAL, private key files, venv, node_modules and build caches while preserving example files. No remote repository was created/pushed.

Backend production entry point (working directory backend/): `python -m app.serve`. It applies non-destructive Alembic migrations, never implicitly seeds, binds 0.0.0.0:PORT and starts **one worker**. Use one backend instance. Seed explicitly once with `python -m app.init_db --seed`; repeating is safe. Linux persistent path example: `DATABASE_URL=sqlite:////data/signal.db`, with /data mounted on durable writable storage. Set actual HTTPS FRONTEND_ORIGIN/WEBSOCKET_ORIGIN and SESSION_COOKIE_SECURE=true. Frontend build: `npm ci`, `npm run build`; production start: `npm run start:production -- --port <frontend-port>`. Public API/WS URLs must be set before build. README.md contains the complete local/hosting command shapes and cookie/proxy prerequisites.

Provider selection remains pending. Resolve account/repository access, persistent-volume availability/cost, an actual public HTTPS origin, WebSocket-capable routing, trusted proxy addresses and one backend instance. Prefer same public origin routing /api/v1 (including WS) and /health to FastAPI, other routes to Next. Unrelated frontend/backend domains are not supported by the default SameSite=Lax cookie strategy. No deployment or paid resource creation occurred.

### Phase 6A manual checklist

1. Sign in normally as alex and in Incognito as maya (123456). Check All/Unread with real incoming messages, search combined with filters, and empty Unread text. Reading/focusing the bottom clears badges and removes the row from Unread without closing its thread.
2. Keep Maya on another chat; send from Alex. Expect one toast and an unread row. Clicking the toast opens the correct chat. Keep Maya focused at the bottom of Alex's chat and send again: no redundant toast. Own sends, receipt changes and reconnect replay must not notify. Hidden/blurred windows may show an in-app toast on return, not an OS notification.
3. Open settings/profile/group details while messages arrive. The obscured thread must not be marked read until the modal closes and the thread is focused at the bottom. Verify Privacy/Notifications/Appearance and Linked devices are reachable Coming Soon categories; no preference or encryption behavior is claimed.
4. Visit main/Chats/conversation menus using mouse and Tab/Escape. New group opens the existing working selection flow. Direct contact/group details show actual data. Calls and Stories show Coming Soon and return without losing the draft.
5. Verify operation results for contact/group creation, group edits and profile saving; failures retain inline messages/retry. Logout clears private notification content and closes its socket. Refresh and restart backend to confirm messaging/receipts/groups/drafts recover without toast replay storms.
6. Review at 1366x768, 1920x1080 and side-by-side windows. Core rail/sidebar/header/composer tokens and existing styles are preserved, apart from required filter space and added overlays.

### Phase 6A verification record

- **27 backend tests passed**, covering all prior auth/contact/message/group regressions, validated production origins/port/path settings, and a real authenticated socket accepting the explicit WEBSOCKET_ORIGIN while rejecting the otherwise allowed HTTP origin. Tests use isolated databases/ports; no project seed/reset was performed.
- **Frontend type checking, ESLint and final production build passed**. The state/contract script verifies real-data All/Unread filtering, incoming message-ID deduplication and suppression for own/system messages, active reading and replay, alongside existing message/receipt/group reconciliation and HTTPS-to-WSS checks.
- **Both production start commands were actually run locally**: backend `python -m app.serve` on port 8000, frontend `npm run start:production -- --port 3000`. The backend applied additive migrations without seeding; Alembic check reports no new operations. Health reports database/status ok. Existing authenticated browser sockets reconnected to the restarted backend (observed in server logs; no browser interaction claim).
- **Live connectivity/CORS and Phase 3B adapter regressions passed** against the restarted servers, including session restoration/logout, independent inboxes, contacts/history, unauthorized access rejection, API/network error handling and no fixture fallback. The frontend application and preserved health-check page respond successfully.
- **Browser verification is pending**: the installed Browser runtime still reports no available browser. New menu/filter/settings/toast DOM interactions, focused-reading suppression, modal focus and desktop screenshots require the manual checklist above. Policy/protocol tests do not replace that review. No hosted test, provider resources, publishing, remote push or paid action occurred.

Phase 6A stops for local review. Publishing, deployment, paid resources, remote pushes and bonuses are not authorized in this checkpoint.
