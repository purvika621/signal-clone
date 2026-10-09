# Signal Desktop design and implementation plan

Phase 1 only. No application has been scaffolded or implemented. Requirements come from all four pages of `Scaler_SDE_Fullstack_Assignment_-_Signal_Clone.pdf`; REQUIREMENTS.md is the acceptance checklist. Deadline supplied by the user: 9 October 2026 at 6:00 pm IST. Prioritize required behavior and desktop fidelity; bonuses follow only if time remains.

## Reference evidence and limits

The [official brand page](https://signal.org/brand/) links the [desktop screen archive](https://signal.org/brand/bundles/Signal%20App%20Screens%20Desktop.zip). Downloaded the archive and visually inspected `Chat.png` and `Group_Chat.png`. It also contains `Story.png` and `Video_Call.png`; those sections may remain placeholders. The marketing frame, macOS traffic lights, and decorative outer texture are not application UI to reproduce in the hosted page.

Additional actual desktop screenshots inspected: a [Windows inbox with Roommates open](https://images.filepuma.com/screenshots/chat_instant_messaging/signal/wa_FP-signal_f1c65969e7e9e7ad88167337486.png), which is cropped before the composer, and a [New chat screen](https://i.sstatic.net/MEnJIFpB.png) showing the rail, back action, search field, and discovery entries. The latter has a red annotation that must not be copied. These screenshots show different client generations; use the official archive's rail-based layout consistently, rather than mixing it with the older Windows top-avatar layout.

Official behavior references: [settings navigation](https://support.signal.org/hc/en-us/articles/360009091591-Navigate-to-Settings), [group creation](https://support.signal.org/hc/en-us/articles/360007319331-Group-chats), [group management](https://support.signal.org/hc/en-us/articles/360050427692-Manage-a-group), and [appearance](https://support.signal.org/hc/en-us/articles/360007320951-Chat-Colors-Wallpaper-and-Themes). These establish entry points and flows; they do not establish pixel geometry for unseen screens.

**Missing visual references:** usable screenshots were obtained for the inbox/open conversation, group thread, composer, and new-chat entry screen. Exact layouts remain unverified for the following. Please provide desktop screenshots of:

1. Global search with matching contacts/conversations and any visible filter state; chat search with results selected.
2. New chat with contact results, and the username/phone lookup or add-contact form.
3. New group member selection, then the group-name/Create step.
4. Group details/member list with an Admin badge, plus add-member and remove-member controls or confirmation.
5. Expanded rail/hamburger menu, Chats overflow menu, and conversation-header overflow menu.
6. Settings open on Privacy, Notifications, and Appearance, including category navigation.

Use one desktop version and theme where possible, with private content redacted. Until these arrive, the corresponding sections below describe proposed behavior and information structure, not verified Signal layouts. Do not substitute a generic chat design or claim exact visual parity for those screens.

## Screen-by-screen UI

### Desktop shell and inbox — visually verified

Three adjacent regions: a narrow navigation rail, a conversation sidebar, and a flexible chat pane. Official screens show a rail with hamburger at top; selected chat icon on a rounded gray tile; calls and stories below; settings gear and profile avatar at bottom. The sidebar has a bold `Chats` heading, compose icon, overflow icon, rounded Search field, and scrollable rows. Fine vertical dividers separate regions. The content viewport fills the browser; omit simulated operating-system window chrome.

Choose the official light group screen as the default theme. Its sidebar/rail are subtly off-white, the chat surface white, and selected row gray. Dark mode is optional; the official direct-chat screen supplies its reference if implemented. Outgoing blue from the direct screen is the proposed default chat color; the group reference demonstrates a configurable red, which is not a requirement to implement color customization.

Starting CSS measurements are design estimates, to be calibrated against the source images: 64-72px rail, 300-340px sidebar, 64-72px chat header, 44-48px row avatars, roughly 72-88px rows, 14px body text, 16px names/header, 12px timestamps, and 20-24px line icons. Use a system sans-serif stack. Do not interpret the large source-image pixels as CSS pixels. Verify a 1440x900 desktop viewport and a smaller laptop viewport.

### Conversation rows — visually verified

Round avatar on the left; bold name, muted preview beneath; activity time at upper right; receipt or blue unread-count badge below it. Long previews wrap/clamp rather than colliding with time. Group previews may prefix a sender name. Selected row has a large rounded gray background and retains its selection while messages arrive. Times vary between relative recent times, clock time, and weekday for older activity.

Sort by latest persisted activity with a stable ID tie-breaker. Incoming messages update preview and order immediately; unread state is per user. Search and an All/Unread filter are required behavior; filter placement is provisional pending a screenshot, since the PDF requires filters without prescribing their labels.

### Open direct chat and header — visually verified

Avatar/name at left of the header; outline video, voice, search, and overflow actions at right. Calls open a Coming Soon surface. The thread scrolls independently while header/composer stay fixed. Incoming bubbles align left; outgoing bubbles align right. Both have large rounded corners and constrained width, with quiet timestamp/receipt metadata at the lower trailing edge. Official dark direct chat shows centered system notices and relative times; use date dividers when messages span days as a proposed threading treatment.

PDF-required online/last-seen labels are an assignment-specific addition: the inspected Signal headers do not show presence. Place a small muted, explicitly mocked subtitle beneath the name, avoiding an invented green presence dot in every avatar. An empty selection or empty thread is a proposed state requiring visual confirmation if exact matching is requested.

### Message thread, receipts, and composer — visually verified baseline

Group incoming messages include participant avatars and colored sender names; outgoing messages do not repeat the current user's avatar. Consecutive messages by the same sender should be grouped with compact spacing. Maintain chronological ordering; preserve reading position when older messages load. Auto-scroll on own send or when already near bottom; otherwise offer a new-message indicator (proposed behavior).

Receipts use the Signal-style circled-check visual vocabulary: pending sending indicator, one outlined check for sent, two outlined checks for delivered, filled double checks for read. The official screenshots visibly show double-check receipts; intermediate states come from the PDF's required state progression and must be checked against a further reference if exact glyph fidelity is needed. Render full absolute date/time in a tooltip or accessible label.

The official composer has an emoji face at left, a rounded `Message` field, then sticker, microphone, and plus icons on the right. Preserve this structure; bonus attachments and unsupported media actions may explain their unavailable state instead of pretending to send. Proposed text behavior: Enter sends, Shift+Enter inserts newline, blank text cannot send, and an active draft replaces the idle microphone with a send action. These keyboard/send states are unverified visually. Typing activity occupies a small line above the composer without moving the header. Sending is optimistic; a failed request retains text and offers retry.

### Search, contacts, and new chat — partial visual verification

The inspected New chat screen replaces the sidebar content with a back arrow/title, rounded `Name, username, or number` input, and entries for `New group`, `Find by username`, and `Find by phone number` with circular icons. Keep the rail and existing chat context. Contact results should show round avatars and names; selecting one opens or creates a single canonical direct conversation.

Proposed global search groups matching contacts and conversations, includes clear/no-results/loading states, and never exposes users' unrelated message history. Chat-header search can search within the active conversation as a useful extension; global message search is not a PDF must-have. Add-contact discovery resolves an existing registered user, allows a local display alias, and rejects duplicates/self-add. Exact result/form layout awaits the requested references.

### Group creation and management — behavior documented, layout unverified

Official group-creation documentation describes Compose > New group > choose contacts > Next > name > Create. Adopt a two-step flow with visible selected members, back/cancel, required group name, and final confirmation. Creator becomes admin. The PDF requires named groups and members; invite links, QR codes, join requests, mentions, descriptions, and advanced permissions are not required.

A group thread follows the verified Group_Chat screen. Group details must list members with Admin labels and expose add/remove only for admins, following official management guidance. Proposed removal uses confirmation and prevents leaving the group with no admin. Non-admin access is enforced in FastAPI, not only hidden in the UI. Group changes can generate centered system messages. Exact panel/modal geometry and menus await screenshots.

### Menus and settings — entry points documented, layout unverified

Verified anchors include rail hamburger/settings gear, Chats overflow, and header overflow. Official support identifies the gear as application settings and conversation overflow as chat settings. Proposed menus expose New chat/New group, required filters, conversation details, and settings; logout is an assignment-specific session action. Menu inventories and item order remain provisional. Use focus management, Escape dismissal, and keyboard access.

Privacy, Notifications, and Appearance must be reachable settings categories. Proposed placeholders explain Coming Soon; local selections may persist without claiming OS integration or real encryption. Keep light theme fixed unless optional dark mode is implemented. Linked devices, stories, and call actions show clear Coming Soon content. Obtain settings screenshots before choosing category dimensions, control styles, and section spacing.

### Mock onboarding — PDF requirement, outside main visual target

Minimal identifier entry > fixed demo OTP > display name/avatar > workspace. Existing users can log in with the same mock verification. Show demo instructions and an immediately usable seeded account. Session survives reload; logout clears it. This is an assignment adaptation, not a reproduction of actual Signal Desktop QR/device linking. Use selected built-in avatar assets or URLs to avoid making optional file attachments a dependency.

## Architecture and SQLite model

Next.js + TypeScript renders UI and maintains normalized client state. FastAPI owns authentication, validation, memberships, persistence, and real-time fan-out. SQLite is authoritative; no core data exists only in browser memory. REST performs durable commands/queries; WebSockets distribute committed updates and ephemeral typing. No actual Signal cryptographic protocol or existing clone repository is used.

All IDs are UUID text except monotonic message/event sequence integers. Store UTC timestamps and display in the viewer's locale. Enable foreign keys, WAL, and a busy timeout; keep write transactions short. One FastAPI worker initially avoids inconsistent in-memory socket registries.

| Table | Proposed fields and relationships |
| --- | --- |
| users | id PK, username UNIQUE nullable, phone_e164 UNIQUE nullable, display_name, avatar_url, created_at; require at least one normalized identifier |
| sessions | id PK, user_id FK users, token_hash UNIQUE, created_at, expires_at, revoked_at; opaque session tokens, never raw tokens in DB |
| contacts | owner_user_id FK users, contact_user_id FK users, alias nullable, created_at; composite PK, forbid self-contact; directional address books |
| conversations | id PK, kind CHECK direct/group, title nullable, avatar_url nullable, created_by FK users, created_at, last_activity_at; group title required |
| direct_pairs | conversation_id PK/FK conversations, user_low_id FK users, user_high_id FK users; UNIQUE ordered pair and enforce low < high; prevents duplicate direct chats |
| conversation_members | conversation_id FK, user_id FK, role CHECK admin/member, joined_at, left_at nullable, last_read_sequence default 0; composite PK; direct chats have two active members, groups at least one active admin |
| messages | sequence INTEGER PK AUTOINCREMENT, id UNIQUE, conversation_id FK, sender_id FK users nullable for system entries, client_message_id, kind CHECK text/system, body, created_at; UNIQUE(sender_id, client_message_id) for retries |
| message_receipts | message_id FK messages(id), recipient_user_id FK users, delivered_at nullable, read_at nullable; composite PK; recipient snapshot at send time, no sender receipt |
| user_settings | user_id PK/FK users, privacy_json, notifications_json, appearance_json, updated_at; validate supported keys; placeholders remain honest |
| user_events | sequence INTEGER PK AUTOINCREMENT, user_id FK users, type, payload_json, created_at; durable replay of committed events, bounded retention |

Indexes: messages(conversation_id, sequence), conversations(last_activity_at), memberships(user_id, left_at), receipts(recipient_user_id, message_id), contacts(owner_user_id), and user_events(user_id, sequence). Case-normalize identifiers before unique checks. Use parameterized SQL and versioned migrations. Optional attachments/reactions/replies/expiry get separate migrations only if selected later.

Unread count derives from incoming text messages beyond the member's read cursor for which a recipient receipt exists. This excludes own sends, system entries, and pre-join messages. Update the cursor monotonically only when the visible conversation has rendered through that sequence; focused visibility is required, not merely socket connectivity. Reading also sets read/delivered receipt times for addressed messages. Historical membership and send-time recipient snapshots prevent newly added members receiving retroactive unread/receipt obligations.

Send transaction checks active membership, inserts the message idempotently, creates recipient receipts, advances conversation activity, and inserts addressed events. Commit before broadcasting. Sent means persisted; delivered means a recipient client acknowledged receipt; read means it acknowledged visible reading. For groups, sender display advances to delivered/read only when all intended recipients reach that state; optional details can show counts. Sending is transient client state. Removed members stop receiving new events and cannot read/write the conversation through API; history access after removal is excluded from this proposed demo.

## Proposed REST API

Use `/api/v1`; all endpoints except mock-auth entry/verification and health require a session. FastAPI derives acting user from the session. Return consistent `{code, message, field_errors?}` errors: 401 unauthenticated, 403 forbidden, 404 missing, 409 conflict, 422 validation. Cursor pagination returns an explicit next cursor; message ordering uses sequence.

| Method/path | Purpose |
| --- | --- |
| POST /auth/challenges | Validate username/phone and start mock registration/login; document fixed OTP |
| POST /auth/verify | Verify demo OTP, create/load user and issue session cookie |
| GET /auth/session | Restore current user/session |
| POST /auth/logout | Revoke session, clear cookie, disconnect its sockets |
| GET, PATCH /me | Read/update display name and avatar |
| GET /users?query= | Discover registered demo users by name/identifier with bounded results |
| GET /contacts?query= | List/search current user's contacts |
| POST /contacts | Add existing user to current user's contacts |
| GET /conversations?query=&filter=all\|unread&cursor= | Membership-scoped list with preview, unread count, latest activity |
| POST /conversations/direct | Get/create canonical conversation with contact_user_id |
| GET /conversations/{id} | Header/details and current-user permissions |
| GET /conversations/{id}/messages?before_sequence=&limit= | Paginated persisted history |
| POST /conversations/{id}/messages | Send text with client_message_id; return authoritative message |
| POST /conversations/{id}/read | Advance visible through_sequence, update unread and receipts |
| POST /groups | Transactionally create group with title and member IDs; creator admin |
| GET /groups/{id}/members | Member list and roles |
| POST /groups/{id}/members | Admin-only add members |
| DELETE /groups/{id}/members/{user_id} | Admin-only removal; protect last admin |
| GET, PATCH /me/settings | Read/store validated demo settings |
| GET /health | Operational readiness; check database availability |

Group renaming/admin promotion and in-chat message search can be added if needed for the reviewed UI; they are not extra PDF must-haves. Presence may be a stable mocked field in user/contact responses. Do not replace real cross-user text messaging with simulated automatic replies.

## WebSocket protocol and reconciliation

Connect to `/api/v1/ws` over WSS, authenticated by the session cookie. Validate Origin. On reconnect send last received event cursor; server replays only events addressed to that user. If cursor is older than retained events, send `sync.required` and refetch conversation list/history. Persist the replay cursor on the client and deduplicate by event ID/message ID. Snapshot and replay handling must prevent a fetch from overwriting newer events.

Envelope: `{event_id?, type, conversation_id?, occurred_at, payload}`. Durable events have user_events sequence as event_id; ephemeral events do not advance replay state. Client-generated identifiers correlate optimistic sends with REST responses and socket echoes.

| Direction/event | Meaning |
| --- | --- |
| Server session.ready | Authenticated identity and replay information |
| Server message.created | Committed message; sender and eligible recipients merge it once |
| Server message.receipt_updated | Recipient delivery/read update; sender recomputes status |
| Server conversation.updated | Preview/order/unread changes for current user |
| Server group.created / group.members_updated | New group or membership change; invalidate scoped details |
| Server conversation.access_revoked | Remove inaccessible group and close active pane after removal |
| Client message.delivered | Acknowledge received message IDs; membership/recipient checked |
| Client conversation.read | Same validated through_sequence semantics as REST read command |
| Client typing.started / typing.stopped | Active member typing state; rate-limited |
| Server typing.updated | Broadcast typing state to other active members |
| Server sync.required / error | Refetch instruction or structured protocol error |
| Both ping / pong | Application heartbeat and dead-connection detection |

Typing expires after approximately five seconds, stops on send/blur, and is not stored. Presence is explicitly mocked initially. Events cannot set another user's receipts. Receipt updates are monotonic and idempotent. Reconnect retries use backoff; failed REST sends retry with the same client_message_id. Fetch persisted history after connection recovery. Catch-up history delivered to a recipient can be acknowledged even if its original live event was missed.

## Seed, deployment, and verification decisions

Seed six fictional users with reusable demo identifiers/avatars, several direct conversations, two named groups, multiple admins/members, and approximately 40 varied text messages. Include read and unread conversations, single/multiple-line text, different days, and mixed receipt states. Seed deterministically and idempotently; never reset a deployed DB at startup. These counts are design choices, since the PDF requires only multiple users/conversations/messages.

Prefer one container-capable host with a persistent disk and reverse proxy: Next.js frontend plus FastAPI `/api` and WebSocket routing under one origin. This simplifies HttpOnly cookie sessions and WSS. SQLite file belongs on the durable volume, not a serverless ephemeral filesystem; single backend worker until shared fan-out is added. If frontend and backend are split, explicitly configure allowed origin, credentialed cookies, HTTPS/WSS, and durable backend storage. Provider is not selected or deployed in Phase 1. Verify its current storage/WebSocket constraints before selecting it.

Tests should focus on behavior: session reload/logout, two-browser real-time delivery, receipt transitions, typing expiry, unread visibility, reconnect without duplication, persistence across backend restart, admin authorization, and duplicate direct/send prevention. Compare screenshots of the shell/thread to the official images; do not claim exact parity for missing references. README must cover local setup, stack, architecture, schema, API, demo accounts, assumptions/mocks, and hosted URLs.

## Small implementation phases after review

Each phase is future work. Do not begin any of them during this task. Estimated slices are relative priorities, not a promise that the PDF's 24-hour effort fits the remaining deadline.

| Phase | Scope | Testable completion condition |
| --- | --- | --- |
| 1. Review and visual reference closure | Approve these documents; obtain missing UI screenshots or explicitly accept provisional layouts | Every required screen has a reference or recorded limitation; core vs bonus scope is agreed |
| 2. Persistence foundation | Only then create frontend/backend structure, SQLite migrations, schema constraints, deterministic seed | Fresh database has multiple usable users/chats/messages; second seed creates no duplicates; data survives restart |
| 3. Mock authentication | Identifier/OTP flow, profile, session cookie, logout | Register new user; set avatar/name; reload remains logged in; logout invalidates REST and WebSocket access |
| 4. Desktop shell and read-only inbox | Rail, list, active thread, verified header/composer geometry | Seeded list sorts correctly; selected direct/group thread displays history; desktop screenshots match reference structure |
| 5. Contacts and discovery | Contact add, conversation/contact search, All/Unread, new-chat flow | Add a contact, find it, open a direct chat twice and receive the same conversation; empty/invalid search states work |
| 6. Durable direct sending | REST send, optimistic status, real-time fan-out, reconnect | Two independent users exchange text without reload; reload/restart retains it; retried send appears exactly once |
| 7. Receipts, unread, and typing | Delivered/read acknowledgments, visible cursor, typing expiry | Offline recipient leaves sent state; receipt acknowledgment advances delivered; focused read advances read; hidden chat remains unread; typing expires |
| 8. Groups | Creation, group fan-out, member view, admin add/remove | Three sessions receive group text; data survives restart; non-admin mutation returns 403; removed member receives no new messages/access |
| 9. Menus, settings, and placeholders | Reference-guided overlays, settings categories, calls/stories/devices placeholders, toasts | All required navigation works; unsupported sections say Coming Soon; forms/menus handle cancel, validation, and focus |
| 10. Core validation and documentation | Meaningful API/integration checks, desktop visual review, README | Every core REQUIREMENTS checkbox has demonstrated evidence; all required README sections present; no required feature displaced by bonus work |
| 11. Hosting and submission | Persistent hosting, HTTPS/WSS, public repository, demo links | Hosted two-user exchange works; redeploy preserves data; public repo contains frontend/backend and README; both submission URLs are verified |
| 12. Optional polish only if time remains | Select bonuses individually; deployment gets priority | Each chosen bonus has a working demonstration and regression check; unfinished bonuses are documented without claiming completion |

Review stop: only REQUIREMENTS.md and DESIGN.md are deliverables now. No scaffolding, feature code, repository publication, or deployment is authorized by this Phase 1 instruction.
