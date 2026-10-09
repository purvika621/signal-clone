# Requirements

Authoritative source: `Scaler_SDE_Fullstack_Assignment_-_Signal_Clone.pdf`, all four pages programmatically extracted with pypdf and visually checked from rendered pages. Page references below refer to that PDF. Unchecked boxes are implementation/submission work, not claims of completion.

User scope: recreate the Signal Desktop messaging application after login as a hosted web app. The desktop conversation workspace is the visual target. A minimal mocked onboarding flow remains required by the PDF; signal.org's visitor website is outside scope. Phase 1 creates only this file and DESIGN.md; implementation waits for review.

## Required stack (p1)

- [ ] Next.js with TypeScript frontend.
- [ ] Python backend: PDF permits FastAPI or Django; use FastAPI as requested.
- [ ] SQLite database with an independently designed schema.
- [ ] Real-time messaging: PDF permits WebSockets or another mechanism; use WebSockets as requested.

## Must-have: authentication and onboarding (p1)

- [ ] Simple mocked authentication/registration flow.
- [ ] Register using a phone number or username.
- [ ] Set a display name and profile avatar.
- [ ] Login.
- [ ] Logout.
- [ ] Persist sessions across reloads.

## Must-have: contacts and conversation list (p1-2)

- [ ] Signal-style main view with a left conversation list and open chat pane.
- [ ] Sort conversations by most recent activity.
- [ ] Search conversations and contacts.
- [ ] Add a new contact.
- [ ] Show unread indicators.
- [ ] Show last-message previews.
- [ ] Show online/last-seen indicators; these may be mocked.

## Must-have: one-to-one messaging (p2)

- [ ] Send and receive text between two users in real time.
- [ ] Display message timestamps.
- [ ] Delivery/read receipts with the single/double-check experience.
- [ ] Typing indicators.
- [ ] Message states: sending, sent, delivered, read.
- [ ] Persist every message in the database.

## Must-have: group messaging (p2)

- [ ] Create a group with a name and members.
- [ ] Send and receive group messages.
- [ ] View group members.
- [ ] Add members using admin controls.
- [ ] Remove members using admin controls.
- [ ] Persist all group data and messages.

## Must-have: Signal experience (p1-3)

- [ ] Closely reproduce Signal's design, UX, navigation, look and feel; the PDF explicitly asks for the same UI/UX rather than a generic chat app.
- [ ] Study Signal UI before implementation.
- [ ] Reproduce conversation-list plus chat-pane navigation and layout.
- [ ] Reproduce message bubbles and threading (message grouping; reply-to is separately optional).
- [ ] Reproduce forms, modals, search, and filters.
- [ ] Notifications/toasts.
- [ ] Privacy settings placeholders.
- [ ] Notification settings placeholders.
- [ ] Appearance settings placeholders.

## Allowed mocks and placeholders (p1-2)

These permissions do not remove the functional must-haves above. Placeholder sections may simply show "Coming Soon".

- [ ] Phone verification may use a fixed OTP.
- [ ] Real phone verification may be mocked.
- [ ] Actual cryptographic key exchange may be mocked.
- [ ] Actual end-to-end encryption may be mocked or simulated.
- [ ] Online/last-seen indicators may be mocked.
- [ ] Voice/video calls may be placeholders.
- [ ] Stories may be a placeholder.
- [ ] Linked devices may be a placeholder.
- [ ] Privacy, notifications, and appearance settings may be placeholders as stated under Signal Experience.

## Optional bonuses (p2-3)

- [ ] Image/file attachments.
- [ ] Emoji message reactions.
- [ ] Reply-to/quoted messages.
- [ ] Functional disappearing messages.
- [ ] Dark mode.
- [ ] Responsive layouts for mobile, tablet, and desktop.
- [ ] Keyboard shortcuts.

## Required seeded data (p3)

- [ ] Seed SQLite so the app is immediately usable.
- [ ] Seed multiple users.
- [ ] Seed multiple conversations.
- [ ] Seed multiple messages.

The PDF specifies no counts. Proposed fixture: six users, several direct chats, two groups, varied timestamps, unread conversations, and receipts; see DESIGN.md. This fixture choice is not an additional PDF requirement.

## Required README contents (p3)

- [ ] Setup instructions.
- [ ] Actual technology stack used.
- [ ] Architecture overview.
- [ ] Database schema.
- [ ] API overview.
- [ ] Assumptions made, including mocks and omitted bonuses.

## Required source, deployment, and submission (p3)

- [ ] Original source code; do not plagiarize an existing clone repository. PDF states plagiarism causes immediate disqualification.
- [ ] Public GitHub repository.
- [ ] Repository contains `frontend/` and `backend/` when implementation begins.
- [ ] Documentation delivered as a README with the contents above.
- [ ] Deploy a working application using a cloud service. PDF examples: Vercel, Netlify, Render, Railway; other services are allowed.
- [ ] Hosted, working demo link.
- [ ] Submit the public GitHub repository link.
- [ ] Submit the deployed application link.

Submission values are not yet available; no links have been invented. Backend hosting must support WebSockets and durable SQLite storage (design constraint for fulfilling persistence).

## Evaluation and code understanding (p1, p3)

- [ ] Functionality: all core features, including real-time messaging, work correctly.
- [ ] UI/UX: visual similarity and original UX patterns.
- [ ] Database design: well-structured schema with proper relationships.
- [ ] Backend/API design: clean, sensible APIs and architecture.
- [ ] Code quality: clean, readable, organized code.
- [ ] Modularity: separation of concerns and reusable components.
- [ ] Code understanding: understand every submitted line and explain implementation decisions during evaluation.

AI assistance is allowed and encouraged, but does not waive understanding or originality.

## Timeline and Phase 1 boundary (p4 and user instruction)

- [ ] Plan around the user-supplied deadline: **9 October 2026, 6:00 pm IST (12:30 UTC)**. The PDF itself says the deadline is communicated separately.
- [ ] Treat the PDF's approximately 24 hours of estimated effort as an estimate, not additional time before today's deadline.
- [ ] Complete and review REQUIREMENTS.md and DESIGN.md before starting implementation.
- [ ] Do not scaffold `frontend/` or `backend/`, write feature code, or deploy during Phase 1.
