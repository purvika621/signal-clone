# Signal Desktop Clone

A browser-hosted recreation of the Signal Desktop messaging application for the Scaler assignment. It reproduces the conversation workspace rather than the signal.org visitor website. The implementation is original; no existing Signal clone repository was copied.

The assignment PDF is preserved at the root. See [REQUIREMENTS.md](REQUIREMENTS.md) for assignment requirements, [DESIGN.md](DESIGN.md) for reference/architecture decisions, and [DEVELOPMENT.md](DEVELOPMENT.md) for detailed contracts and coverage. The source repository is published; hosting and a verified demo link remain pending.

Source repository: [purvika621/signal-clone](https://github.com/purvika621/signal-clone). The single-origin Docker deployment package is tested locally; [DEPLOYMENT.md](DEPLOYMENT.md) contains Railway settings, persistent SQLite requirements and acceptance checks. Hosting remains pending approval. This package supersedes the split-provider deployment proposal below for the no-custom-domain setup; existing Windows development commands remain valid.

## Stack and features

- Frontend: Next.js 16.4.0, React 19.3.0, TypeScript 5.9, App Router, Tailwind CSS 4.3.3, shared design tokens and CSS modules; **Node 24.x**.
- Backend: **Python 3.13.x**, FastAPI 0.143.0, Uvicorn 0.54.0, SQLAlchemy 2.0.54, Pydantic 2.14.0, Pydantic Settings 2.15.0, Alembic 1.20.0, **SQLite and WebSockets**. Requirements are pinned and the frontend lockfile is included.
- Mock registration/login, editable name/avatar, persistent server-validated sessions and logout.
- User-specific contacts/inbox, contact discovery/addition, canonical direct chats, conversation search, All/Unread filters, previews and online/last-seen state.
- Persisted direct/group text messaging, Enter/Shift+Enter composer, pending/sent/failed states with safe retry, typing, delivered/read receipts and unread clearing.
- Authenticated realtime delivery, multiple sessions, bounded reconnect/replay, authoritative catch-up and preserved drafts; no polling substitute or fixture fallback.
- Named groups, roster/Admin labels, rename, admin add/remove/role controls, confirmed leaving, last-admin protection and immediate access revocation.
- Signal-style desktop layout, navigation menus, in-app toasts and operation feedback. Incoming notifications suppress duplicates, own/system messages, replay and active reading; browser notification permission is never requested.

Privacy and Notifications settings, Calls, Stories and Linked devices are reachable **Coming Soon** placeholders. SMS, pairing, key exchange and real Signal encryption are mocked/omitted; messages are plaintext demo data. Optional attachments, quoted replies, disappearing messages are deferred. In-chat message search is not implemented; required conversation/contact search works.

The official Chat.png/Group_Chat.png desktop brand references guide the reviewed layout; OS/marketing frames are excluded. Stock avatar attribution is in frontend/public/avatars/SOURCES.md. Exact unseen menu/settings geometry is provisional as recorded in DESIGN.md.

## Windows local setup

Use Python 3.13 and Node 24 (verified with Python 3.13.5 and Node 24.15.0). Replace the checkout path if needed. A virtual environment is used without activation or execution-policy changes.

```powershell
Set-Location F:\signal-clone\backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
.\.venv\Scripts\python.exe -m app.init_db --seed

Set-Location F:\signal-clone\frontend
if (-not (Test-Path -LiteralPath .env.local)) { Copy-Item -LiteralPath .env.example -Destination .env.local }
npm ci
```

Backend, terminal 1:

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Frontend, terminal 2:

```powershell
Set-Location F:\signal-clone\frontend
npm run dev
```

Frontend: http://localhost:3000. Backend health: http://localhost:8000/health. API docs: http://localhost:8000/docs. Stop with Ctrl+C. For local production frontend use `npm run build`, then `npm start`; rebuild before restarting after source/public environment changes. Stop the frontend before reinstalling dependencies on Windows to avoid native binary locks.

## Environment and initialization

Commit only the provided local/production **example** environment files, not actual `.env`/`.env.local` files. Backend process environment overrides backend/.env. Frontend public values are embedded **at build time** and must never contain secrets.

| Variable | Value/behavior |
| --- | --- |
| DATABASE_URL | Local `sqlite:///./data/signal.db`, relative to backend/; Linux production `sqlite:////data/signal.db` on a durable volume |
| FRONTEND_ORIGIN | Exact HTTP(S) browser origin; local `http://localhost:3000`; credentialed CORS and HTTP origin validation |
| WEBSOCKET_ORIGIN | Optional exact HTTP(S) browser origin, not WS/WSS; defaults to FRONTEND_ORIGIN |
| SESSION_COOKIE_SECURE | false for local HTTP; true behind production HTTPS |
| SESSION_DAYS / MOCK_OTP | 7 days; public fixed demo code 123456 (not a secret) |
| SQLITE_BUSY_TIMEOUT_MS / APP_NAME | 5000; Signal Desktop Clone API |
| PORT | Production backend entry point reads platform port; default 8000 |
| NEXT_PUBLIC_API_URL | Local `http://localhost:8000`; public API origin without /api/v1 |
| NEXT_PUBLIC_WS_URL | Optional full socket endpoint; otherwise derived from API origin using WS/WSS |

`localhost` and `127.0.0.1` are different CORS origins. Production examples use deliberately non-working example.invalid domains; replace them with actual public origins when hosting is authorized.

`python -m app.init_db` applies versioned migrations without resetting data. `--seed` adds missing deterministic demo records and is repeatable without overwriting profiles, messages, memberships, receipts or read cursors. Fresh seed: six users, four direct conversations, two groups and forty messages. Current migration: 0004. Never delete the database or substitute create_all for an upgrade. Production startup migrates but never implicitly seeds.

## Demo and two-user testing

Login identifiers: **alex**, **maya**, **kai**, **paige**, **julian**, **sam**. Continue, use mock code **123456**, and select a profile name/avatar if prompted. New valid usernames or international phone numbers register through the same mock flow. Anyone with the displayed code can access demo identities; use fictional content.

1. Sign in as Alex normally and Maya in Incognito. Open their direct chat; send both ways, test multiline text, typing, receipts, refresh and logout isolation.
2. Keep Maya on another chat and send from Alex: expect one toast, preview/unread update and an Unread filter row. Open/focus the chat at the bottom to clear unread/read receipts. Active reading and reconnect replay should not generate redundant toasts.
3. Test settings/menu placeholders, contact addition and group administration. Use Kai in another browser/profile for three-user group tests; Incognito windows in one browser share cookies.
4. Close/reopen a recipient or restart the single backend: missed messages should recover once, drafts survive and sessions restore. Check desktop and side-by-side layouts.

The owner reports **19/19 manual browser checks passed** through Phase 6A. This is manual testing, not browser automation. Automated results are documented separately below and in DEVELOPMENT.md.

## Architecture, database and API

Next decodes API JSON into typed contracts and reconciles optimistic/REST/socket records by stable IDs. FastAPI derives identity from an opaque HttpOnly cookie; SQLite stores only its SHA-256 hash plus expiry/revocation. The server enforces membership/admin/recipient permissions. Durable commands commit messages, receipts and addressed events before confirmation/broadcast; typing/presence are ephemeral.

**One backend worker and one backend instance** are required because socket/typing registries are in memory. Multi-worker/replica support would require a shared broker and additional concurrent-admin locking.

| Tables | Purpose |
| --- | --- |
| users, sessions, contacts | Profiles, unique identifiers, hashed sessions and directional address books |
| conversations, direct_pairs | Direct/group metadata and a unique canonically ordered direct user pair |
| conversation_members | Unique conversation/user membership, role, join/leave time and read cursor |
| messages, message_receipts | Ordered durable messages, unique sender/client ID and per-recipient delivered/read timestamps |
| message_reactions | Unique message/user/emoji records; message reaction revision prevents stale updates |
| user_events | Addressed durable replay sequences with bounded retention |
| group_creations | Immutable creator/request intent for duplicate-safe group creation |
| user_settings | Storage prepared for future preferences; Privacy/Notifications are placeholders; appearance is stored locally in the browser |

Foreign keys, WAL, checks, indexes and unique constraints protect the schema. Unread excludes own/system/pre-join messages. Sent means committed; delivered means a recipient acknowledgement; read means focused/visible reading at the bottom. Group aggregate receipts require all original recipients. Historical receipts remain after removal, so an old receipt may remain incomplete. Active members see full pre-join history without retroactive unread/receipt obligations; departed users lose API access. The last admin must promote another member before leaving/demotion.

REST routes use `/api/v1`: auth challenges/verify/session/logout; GET/PATCH `/me`; users/contacts; conversations/direct/history/send/delivered/read; pending delivery; groups/details/rename/members/roles/removal/leave. WebSocket: `/api/v1/ws?cursor=N`, with cookie authentication and explicit Origin validation. `/health` and `/docs` are outside the prefix. Errors consistently return `{code, message, field_errors?}`. Detailed contracts and schema are in DEVELOPMENT.md and live OpenAPI docs.

## Automated checks

```powershell
Set-Location F:\signal-clone\backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check

Set-Location F:\signal-clone\frontend
npm run typecheck
npm run lint
npm run build
npm run verify:messaging-state
# With both local servers running:
npm run verify:connectivity
npm run verify:phase3b
```

Backend tests use isolated temporary SQLite databases and real local HTTP/WebSocket servers; they never reset the project database. Frontend policy/adapter checks are not browser automation. Phase 7A reran the existing suite: **27 backend tests, type checking, lint and production build passed**.

## Production deployment prerequisites

The prepared single-origin Railway Docker package is documented in DEPLOYMENT.md; cloud publishing remains pending approval. Require HTTPS/WebSocket upgrades, a writable persistent volume that survives restart/redeploy, and one backend instance. SQLite must not live on ephemeral/serverless disk. Resolve account/trial access, volume availability/cost and public origin before creating resources. The following separate-process commands describe the underlying services; the Docker package handles their startup and proxy automatically.

Prefer one public origin: reverse-proxy `/api/v1/*` (including WS), `/health`, `/docs` and `/openapi.json` to FastAPI, other routes/assets to Next. Preserve paths, cookies and Origin and enable WebSocket upgrade headers/timeouts. Default SameSite=Lax cookies require same-origin or same-site hosting; unrelated frontend/backend domains need a reviewed cookie strategy.

Backend working directory backend/, Python environment isolated:

```sh
python -m pip install -r requirements.txt
python -m app.init_db --seed  # explicit repeatable demo initialization
python -m app.serve          # migrate, bind 0.0.0.0:PORT, one worker
```

Set `DATABASE_URL=sqlite:////data/signal.db` with durable /data storage, actual HTTPS FRONTEND_ORIGIN/WEBSOCKET_ORIGIN, SESSION_COOKIE_SECURE=true and platform PORT. Configure FORWARDED_ALLOW_IPS only for actual trusted proxy addresses. Back up SQLite using its online backup facility or while stopped; do not discard active WAL files.

Frontend working directory frontend/, public API/WS URLs configured before build:

```sh
npm ci
npm run build
npm run start:production -- --port "$PORT"
```

Each process needs its own internal port. The Docker package runs Next on 3000, FastAPI on 8000 and Nginx on the public PORT. See DEPLOYMENT.md for Railway instructions and local container checks. The verified hosted demo link will be added after deployment and hosted testing. No deployment is claimed complete.

## Appearance and keyboard shortcuts

Open Settings → Appearance and choose Light, Dark, or System. System follows your operating system automatically. The preference is stored locally per browser, survives refresh/logout, and is shared across tabs; it is not a server-side account setting. Browser storage must be available for persistence.

- Ctrl/Cmd+K focuses conversation search.
- Ctrl/Cmd+Shift+N opens New chat.
- Escape closes the topmost menu/dialog; in group details it dismisses a confirmation/member picker first. It also closes the sidebar new-chat flow. Message drafts are retained.
- Enter sends in the composer; Shift+Enter inserts a newline. IME composition does not send or trigger shortcuts. Navigation shortcuts are ignored in modal dialogs and unrelated editable inputs.

These bonuses do not change mock authentication or Chrome Safe Browsing status. Browser visual/regression checks for the bonus checkpoint remain pending; earlier manual results describe earlier phases.

Minimal responsive layout: at 640px and below, show the conversation list or selected chat; the chat header back button returns to the list and keeps drafts. Tablets retain the compact sidebar/chat layout, and desktop proportions remain unchanged. Both themes share these breakpoints.

## Emoji reactions

Hover/focus a persisted text message (the reaction button is visible on touch devices), open the smile button, and choose ❤️ 😂 👍 😮 😢 🎉. Tap a selected emoji or your highlighted count to remove your reaction. Counts include every reacting user; one user may select multiple different emoji. Mutations are idempotent, membership checked, stored in SQLite, and delivered through the existing authenticated WebSocket/replay flow. Reactions do not alter inbox ordering or unread counts. System/pending messages cannot be reacted to.

Migration 0004 adds a reaction table and revision column without resetting data; normal production startup applies it. These final bonuses require owner browser inspection; automated protocol/state checks do not claim UI verification.
