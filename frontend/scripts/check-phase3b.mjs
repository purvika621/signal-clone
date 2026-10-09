// Live typed-adapter checks. Node cookie handling is explicit; browser rendering
// and browser-enforced cookie behavior must still be reviewed manually.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

const transpile = (source) => ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const moduleUrl = (source) => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const utilityUrl = moduleUrl(transpile(await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8")));
const adapterSource = transpile(await readFile(new URL("../src/features/messaging/api.ts", import.meta.url), "utf8")).replace('"@/lib/api"', JSON.stringify(utilityUrl));
const api = await import(moduleUrl(adapterSource));
const { ApiError } = await import(utilityUrl);
const originalFetch = globalThis.fetch;
let cookie = "";
let lastCookieHeader = "";
globalThis.fetch = async (url, options = {}) => {
  const headers = new Headers(options.headers);
  headers.set("Origin", process.env.FRONTEND_ORIGIN || "http://localhost:3000");
  if (cookie) headers.set("Cookie", cookie);
  const response = await originalFetch(url, { ...options, headers });
  lastCookieHeader = response.headers.get("set-cookie") || "";
  if (lastCookieHeader) cookie = lastCookieHeader.split(";")[0];
  return response;
};

async function login(identifier) {
  const challenge = await api.challenge(identifier);
  const session = await api.signIn(challenge.identifier, challenge.mock_code);
  assert.match(lastCookieHeader, /HttpOnly/);
  assert.deepEqual(await api.restoreSession(), session);
  return session;
}
let alexCookie = "", mayaCookie = "";
try {
  await assert.rejects(api.restoreSession(), (e) => e instanceof ApiError && e.status === 401);
  const alex = await login("alex"); alexCookie = cookie;
  const inbox = await api.getInbox();
  assert.ok(inbox.some((c) => c.kind === "direct") && inbox.some((c) => c.kind === "group"));
  for (const conversation of inbox) {
    const messages = await api.getHistory(conversation.id, alex.user.id);
    if (conversation.latest_message === null) assert.equal(messages.length, 0);
    else assert.ok(messages.length > 0);
    assert.ok(messages.every((m) => m.outgoing === (m.sender.id === alex.user.id)));
    const view = api.conversationView(conversation, alex.user.id, messages);
    assert.equal(view.unread, conversation.unread_count);
    assert.equal(view.messages.length, messages.length);
  }
  const contacts = await api.getContacts("maya");
  assert.equal(contacts.length, 1);
  const direct1 = await api.openDirect(contacts[0].user.id);
  const direct2 = await api.openDirect(contacts[0].user.id);
  assert.equal(direct1.id, direct2.id);
  console.log("PASS: typed API adapter restores Alex's session, contacts, direct/group history and receipts; existing direct chat reopens with the same ID.");
  cookie = "";
  const maya = await login("maya"); mayaCookie = cookie;
  assert.notEqual(maya.user.id, alex.user.id);
  const mayaInbox = await api.getInbox();
  assert.ok(mayaInbox.every((c) => c.kind === "group" || c.other_user.id !== maya.user.id));
  const excluded = inbox.find((c) => !mayaInbox.some((m) => m.id === c.id));
  assert.ok(excluded);
  await assert.rejects(api.getHistory(excluded.id, maya.user.id), (e) => e instanceof ApiError && e.status === 403);
  console.log("PASS: independent Maya session has its own inbox; unauthorized history is rejected.");
  await api.signOut();
  await assert.rejects(api.restoreSession(), (e) => e instanceof ApiError && e.status === 401);
  globalThis.fetch = async () => new Response(JSON.stringify({ code: "unavailable", message: "Database temporarily unavailable. Please retry" }), { status: 503, headers: { "Content-Type": "application/json" } });
  await assert.rejects(api.getInbox(), (e) => e instanceof ApiError && e.status === 503 && api.errorMessage(e).includes("temporarily unavailable"));
  globalThis.fetch = async () => { throw new TypeError("fetch failed"); };
  await assert.rejects(api.getInbox(), (e) => api.errorMessage(e).includes("Check the backend connection"));
  console.log("PASS: API 503 and network failure reject with useful errors; no fixture data returned. Logout invalidates the session.");
} finally {
  globalThis.fetch = originalFetch;
  for (const saved of [alexCookie, mayaCookie]) {
    if (saved) await originalFetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/auth/logout`, { method: "POST", headers: { Cookie: saved, Origin: process.env.FRONTEND_ORIGIN || "http://localhost:3000" } });
  }
}
console.log("Browser interaction, refresh and visible error-state inspection remain manual checks.");
