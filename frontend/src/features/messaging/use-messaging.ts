"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { PreviewMessage } from "./types";
import { shouldNotifyIncoming } from "./notifications";
import type { Message } from "./api";
import { errorMessage, getHistory, getInbox, markDelivered, markRead, messageView, parseLiveEvent, pendingDelivery, profile, sendMessage, setReaction, websocketUrl, type Conversation, type User } from "./api";

type Pending = { id: string; conversationId: string; text: string; createdAt: string; state: "sending" | "failed"; failure?: string };
type Thread = { messages: PreviewMessage[]; loaded: boolean; error?: string };
const rank = { sent: 1, delivered: 2, read: 3 };
export function mergeMessages(previous: PreviewMessage[], incoming: PreviewMessage[]): PreviewMessage[] {
  const map = new Map(previous.map((m) => [m.id, m]));
  for (const message of incoming) {
    const old = map.get(message.id);
    map.set(message.id, { ...old, ...message, reactions: (old?.reactionVersion ?? 0) > (message.reactionVersion ?? 0) ? old?.reactions : message.reactions, reactionVersion: Math.max(old?.reactionVersion ?? 0, message.reactionVersion ?? 0), receipt: old?.receipt && (!message.receipt || rank[old.receipt] > rank[message.receipt]) ? old.receipt : message.receipt });
  }
  return [...map.values()].sort((a, b) => (a.sequence ?? Number.MAX_SAFE_INTEGER) - (b.sequence ?? Number.MAX_SAFE_INTEGER) || a.id.localeCompare(b.id));
}
function storage(key: string): unknown { try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch { return null; } }
function savedDrafts(key: string): Record<string, string> {
  if (typeof window === "undefined") return {};
  const value = storage(key);
  return value && typeof value === "object" && !Array.isArray(value) ? Object.fromEntries(Object.entries(value).filter(([, v]) => typeof v === "string")) : {};
}
function savedPending(key: string): Pending[] {
  if (typeof window === "undefined") return [];
  const value = storage(key);
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is Pending => v && typeof v === "object" && typeof v.id === "string" && typeof v.conversationId === "string" && typeof v.text === "string" && typeof v.createdAt === "string" && Number.isFinite(Date.parse(v.createdAt)))
    .map((v) => ({ ...v, state: "failed", failure: "Unconfirmed after refresh. Retry safely with the same message ID." }));
}
const order = (items: Conversation[]) => items.sort((a, b) => b.last_activity_at.localeCompare(a.last_activity_at) || a.id.localeCompare(b.id));

export function useMessaging(user: User, onIncoming: (conversation: Conversation, message: Message) => void, readingEnabled = true) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [threads, setThreads] = useState<Record<string, Thread>>({});
  const [inboxStatus, setInboxStatus] = useState<"loading" | "ready" | "error">("loading");
  const [inboxError, setInboxError] = useState("");
  const [connection, setConnection] = useState("Connecting…");
  const [notice, setNotice] = useState("");
  const [drafts, setDrafts] = useState(() => savedDrafts(`drafts:${user.id}`));
  const [pending, setPending] = useState(() => savedPending(`pending:${user.id}`));
  const [typing, setTyping] = useState<Record<string, { userId: string; name: string; expires: number }[]>>({});
  const [pageActive, setPageActive] = useState(false);
  const [atBottom, setAtBottom] = useState(true);
  const [readTick, setReadTick] = useState(0);
  const socket = useRef<WebSocket | null>(null);
  const selectedRef = useRef<string | null>(null);
  const initialized = useRef(false);
  const alive = useRef(true);
  const revision = useRef(0);
  const versions = useRef<Record<string, number>>(Object.fromEntries([...Object.keys(drafts), ...pending.map((p) => p.conversationId)].map((id) => [id, 0])));
  const inboxGeneration = useRef(0);
  const historyControllers = useRef<Record<string, AbortController>>({});
  const userRef = useRef(user);
  const readThrough = useRef<Record<string, number>>({});
  const reading = useRef(new Set<string>());
  const lastTyping = useRef<Record<string, number>>({});
  const typingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recoveryBusy = useRef(false);
  const revoked = useRef(new Set<string>());
  const [groupChanges, setGroupChanges] = useState<Record<string, number>>({});
  const readingActive = useRef(false);
  const notifiedMessages = useRef(new Set<string>());
  useEffect(() => { userRef.current = user; }, [user]);
  useEffect(() => { try { sessionStorage.setItem(`drafts:${user.id}`, JSON.stringify(drafts)); sessionStorage.setItem(`pending:${user.id}`, JSON.stringify(pending)); } catch { /* The in-memory draft still works when storage is blocked. */ } }, [drafts, pending, user.id]);

  const acceptMessages = useCallback((id: string, messages: PreviewMessage[], loaded = false) => {
    if (revoked.current.has(id)) return;
    setThreads((previous) => ({ ...previous, [id]: { messages: mergeMessages(previous[id]?.messages ?? [], messages), loaded: loaded || previous[id]?.loaded || false } }));
    const clientIds = new Set(messages.filter((m) => m.outgoing).map((m) => m.clientId));
    setPending((previous) => previous.filter((m) => !clientIds.has(m.id)));
  }, []);
  const acceptConversation = useCallback((item: Conversation, stamp = ++revision.current) => {
    if (revoked.current.has(item.id)) return;
    versions.current[item.id] = stamp;
    setConversations((previous) => order([item, ...previous.filter((c) => c.id !== item.id)]));
  }, []);
  const revokeConversation = useCallback((id: string) => {
    revoked.current.add(id);
    versions.current[id] = ++revision.current;
    historyControllers.current[id]?.abort();
    setConversations((items) => items.filter((c) => c.id !== id));
    const omit = <T,>(previous: Record<string, T>) => Object.fromEntries(Object.entries(previous).filter(([key]) => key !== id));
    setThreads(omit); setDrafts(omit); setTyping(omit);
    setPending((items) => items.filter((p) => p.conversationId !== id));
    delete readThrough.current[id];
    if (selectedRef.current === id) {
      selectedRef.current = null; setSelectedId(null);
      const url = new URL(window.location.href); url.searchParams.delete("conversation"); window.history.replaceState(null, "", url);
    }
  }, []);
  const loadInbox = useCallback(async () => {
    const generation = ++inboxGeneration.current, stamp = revision.current;
    try {
      const items = await getInbox();
      if (!alive.current || generation !== inboxGeneration.current) return;
      const authoritativeIds = new Set(items.map((c) => c.id));
      for (const id of Object.keys(versions.current)) {
        if (!authoritativeIds.has(id) && (versions.current[id] ?? 0) <= stamp) revokeConversation(id);
      }
      if (selectedRef.current && !authoritativeIds.has(selectedRef.current) && (versions.current[selectedRef.current] ?? 0) <= stamp) revokeConversation(selectedRef.current);
      for (const item of items) {
        if ((versions.current[item.id] ?? 0) <= stamp) revoked.current.delete(item.id);
        versions.current[item.id] ??= stamp;
      }
      setConversations((previous) => {
        const current = new Map(previous.map((c) => [c.id, c]));
        const ids = new Set(items.map((c) => c.id));
        return order([...items.filter((c) => !revoked.current.has(c.id)).map((c) => (versions.current[c.id] ?? 0) > stamp ? current.get(c.id) ?? c : c), ...previous.filter((c) => !ids.has(c.id) && !revoked.current.has(c.id) && (versions.current[c.id] ?? 0) > stamp)]);
      });
      setInboxStatus("ready");
      if (!initialized.current) {
        initialized.current = true;
        const saved = new URL(window.location.href).searchParams.get("conversation");
        const id = saved && items.some((c) => c.id === saved) ? saved : items[0]?.id ?? null;
        selectedRef.current = id; setSelectedId(id);
      }
    } catch (e) { if (alive.current && generation === inboxGeneration.current) { setInboxError(errorMessage(e)); setInboxStatus("error"); } }
  }, [revokeConversation]);
  const loadHistory = useCallback(async (id: string) => {
    historyControllers.current[id]?.abort();
    const controller = new AbortController(); historyControllers.current[id] = controller;
    try {
      const messages = await getHistory(id, user.id, controller.signal);
      if (alive.current && !controller.signal.aborted) acceptMessages(id, messages, true);
    } catch (e) { if (alive.current && !controller.signal.aborted) setThreads((previous) => ({ ...previous, [id]: { messages: previous[id]?.messages ?? [], loaded: true, error: errorMessage(e) } })); }
  }, [acceptMessages, user.id]);
  const deliver = useCallback(async (id: string, ids: string[]) => {
    for (let i = 0; i < ids.length; i += 100) await markDelivered(id, ids.slice(i, i + 100));
  }, []);
  const recoverDelivery = useCallback(async () => {
    if (recoveryBusy.current) return;
    recoveryBusy.current = true;
    try {
      while (alive.current) {
        const groups = await pendingDelivery();
        if (groups.length === 0) break;
        for (const group of groups) {
          // Receive and validate the actual persisted content before claiming
          // delivery of missed messages, including chats that are not selected.
          const messages = await getHistory(group.conversation_id, user.id);
          if (!alive.current) break;
          acceptMessages(group.conversation_id, messages, true);
          await deliver(group.conversation_id, group.message_ids);
        }
      }
    } catch (e) { if (alive.current) setNotice(errorMessage(e)); } finally { recoveryBusy.current = false; }
  }, [acceptMessages, deliver, user.id]);

  useEffect(() => {
    alive.current = true;
    const controllers = historyControllers.current;
    let stopped = false, failures = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined;
    let cursor = 0;
    try { cursor = Number(sessionStorage.getItem(`events:${user.id}`)) || 0; } catch { /* A fresh authoritative sync still recovers. */ }
    function connect() {
      if (stopped) return;
      let ws: WebSocket;
      try { ws = new WebSocket(websocketUrl(cursor)); } catch (e) { setConnection("Disconnected"); setNotice(errorMessage(e)); return; }
      socket.current = ws;
      let synced = false;
      ws.onmessage = (frame) => {
        if (stopped || socket.current !== ws) return;
        try {
          const event = parseLiveEvent(JSON.parse(frame.data));
          if (event.eventId !== undefined) {
            if (event.eventId <= cursor) return;
            cursor = event.eventId;
            try { sessionStorage.setItem(`events:${user.id}`, String(cursor)); } catch { /* Recovery does not require local storage. */ }
          }
          if (event.type === "session.ready") {
            if (event.userId !== user.id) { ws.close(); setNotice("Session identity changed. Please reload."); return; }
            cursor = Math.min(cursor, event.cursor ?? cursor);
            failures = 0; setConnection("Connected"); setNotice("");
            heartbeat = setInterval(() => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "ping" })); }, 15000);
          }
          if (event.type === "sync.required") {
            synced = true;
            cursor = Math.max(cursor, event.cursor ?? 0);
            try { sessionStorage.setItem(`events:${user.id}`, String(cursor)); } catch { /* Optional recovery cursor. */ }
            void loadInbox(); if (selectedRef.current) void loadHistory(selectedRef.current);
            void recoverDelivery(); setReadTick((n) => n + 1);
          }
          if (event.conversation) {
            if (event.type === "group.created" || event.type === "group.members_updated") {
              revoked.current.delete(event.conversation.id);
              setGroupChanges((previous) => ({ ...previous, [event.conversation!.id]: (previous[event.conversation!.id] ?? 0) + 1 }));
            }
            acceptConversation(event.conversation);
            const messages = event.messages ?? [];
            acceptMessages(event.conversation.id, messages.map((m) => messageView(m, user.id)));
            if (event.type === "message.created") {
              for (const message of messages) {
                const reading = readingActive.current && selectedRef.current === event.conversation.id && document.visibilityState === "visible" && document.hasFocus();
                if (shouldNotifyIncoming(message, user.id, reading, synced, notifiedMessages.current)) onIncoming(event.conversation, message);
              }
              const received = messages.filter((m) => m.sender?.id !== user.id && m.kind === "text").map((m) => m.id);
              if (received.length) void deliver(event.conversation.id, received).catch((e) => { if (!stopped) setNotice(errorMessage(e)); });
            }
          }
          if (event.type === "conversation.access_revoked") {
            revokeConversation(event.conversationId!);
            setNotice("You are no longer a member of that group.");
          }
          if (event.type === "presence.updated") {
            setConversations((items) => items.map((c) => c.other_user && c.other_user.id === event.userId ? { ...c, other_user: { ...c.other_user, online: event.online!, last_seen_at: event.lastSeen ?? null } } : c));
          }
          if (event.type === "typing.updated" && event.userId !== user.id && !revoked.current.has(event.conversationId!)) {
            setTyping((previous) => { const id = event.conversationId!; const entries = (previous[id] ?? []).filter((t) => t.userId !== event.userId); return { ...previous, [id]: event.typing ? [...entries, { userId: event.userId!, name: event.name!, expires: event.expires! }] : entries }; });
          }
          if (event.error) setNotice(event.error);
        } catch (e) { setNotice(errorMessage(e)); }
      };
      ws.onerror = () => ws.close();
      ws.onclose = (event) => {
        if (heartbeat) clearInterval(heartbeat);
        if (stopped || socket.current !== ws) return;
        setTyping({});
        if (event.code === 1008) { setConnection("Session ended — reload to sign in"); return; }
        const delay = Math.min(15000, 1000 * 2 ** Math.min(failures++, 4));
        setConnection("Disconnected — reconnecting…");
        reconnectTimer = setTimeout(connect, delay);
      };
    }
    connect(); void loadInbox();
    const expiry = setInterval(() => setTyping((previous) => Object.fromEntries(Object.entries(previous).map(([id, entries]) => [id, entries.filter((t) => t.expires > Date.now())]))), 1000);
    return () => {
      stopped = true; alive.current = false;
      clearTimeout(reconnectTimer); clearInterval(heartbeat); clearInterval(expiry);
      if (typingTimer.current) clearTimeout(typingTimer.current);
      for (const controller of Object.values(controllers)) controller.abort();
      socket.current?.close(); socket.current = null;
    };
  }, [user.id, acceptConversation, acceptMessages, deliver, loadHistory, loadInbox, recoverDelivery, revokeConversation, onIncoming]);
  useEffect(() => {
    if (!selectedId) return;
    void loadHistory(selectedId);
    const controllers = historyControllers.current;
    return () => controllers[selectedId]?.abort();
  }, [selectedId, loadHistory]);
  useEffect(() => {
    const update = () => setPageActive(document.visibilityState === "visible" && document.hasFocus());
    document.addEventListener("visibilitychange", update); window.addEventListener("focus", update); window.addEventListener("blur", update);
    update();
    return () => { document.removeEventListener("visibilitychange", update); window.removeEventListener("focus", update); window.removeEventListener("blur", update); };
  }, []);
  const currentThread = selectedId ? threads[selectedId] : undefined;
  useEffect(() => { readingActive.current = readingEnabled && pageActive && atBottom && !!currentThread?.loaded && !currentThread.error; }, [readingEnabled, pageActive, atBottom, currentThread]);
  useEffect(() => {
    if (!readingEnabled || !selectedId || !pageActive || !atBottom || !currentThread?.loaded || currentThread.error) return;
    const through = Math.max(0, ...currentThread.messages.map((m) => m.sequence ?? 0));
    if (!through || through <= (readThrough.current[selectedId] ?? 0) || reading.current.has(selectedId)) return;
    const id = selectedId, stamp = revision.current; reading.current.add(id);
    let succeeded = false;
    markRead(id, through).then((conversation) => {
      if (!alive.current) return;
      readThrough.current[id] = Math.max(readThrough.current[id] ?? 0, through);
      succeeded = true;
      if ((versions.current[id] ?? 0) <= stamp) acceptConversation(conversation);
    }).catch((e) => { if (alive.current) setNotice(errorMessage(e)); }).finally(() => { reading.current.delete(id); if (alive.current && succeeded) setReadTick((n) => n + 1); });
  }, [selectedId, currentThread, pageActive, atBottom, connection, readTick, acceptConversation, readingEnabled]);

  function typingCommand(id: string, active: boolean) {
    const ws = socket.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: active ? "typing.started" : "typing.stopped", conversation_id: id }));
  }
  function stopTyping(id = selectedRef.current) { if (typingTimer.current) clearTimeout(typingTimer.current); if (id) { typingCommand(id, false); delete lastTyping.current[id]; } }
  useEffect(() => { if (!pageActive && selectedId) { const ws = socket.current; if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "typing.stopped", conversation_id: selectedId })); } }, [pageActive, selectedId]);
  function select(id: string | null) {
    const changed = selectedRef.current !== id;
    stopTyping(); selectedRef.current = id; initialized.current = true; setSelectedId(id);
    if (changed) setAtBottom(true);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("conversation", id); else url.searchParams.delete("conversation");
    window.history.replaceState(null, "", url);
  }
  function setDraft(text: string) {
    if (!selectedId) return;
    const id = selectedId; setDrafts((previous) => ({ ...previous, [id]: text }));
    if (!text.trim()) { stopTyping(id); return; }
    if (Date.now() - (lastTyping.current[id] ?? 0) >= 1200) { typingCommand(id, true); lastTyping.current[id] = Date.now(); }
    if (typingTimer.current) clearTimeout(typingTimer.current);
    typingTimer.current = setTimeout(() => stopTyping(id), 3000);
  }
  async function submitPending(item: Pending) {
    setPending((previous) => [...previous.filter((p) => p.id !== item.id), { ...item, state: "sending", failure: undefined }]);
    try {
      const message = await sendMessage(item.conversationId, item.id, item.text);
      if (alive.current) { acceptMessages(item.conversationId, [messageView(message, user.id)]); void loadInbox(); }
    } catch (e) { if (alive.current) setPending((previous) => previous.map((p) => p.id === item.id ? { ...p, state: "failed", failure: errorMessage(e) } : p)); }
  }
  function send() {
    if (!selectedId) return;
    const body = (drafts[selectedId] ?? "").trim(); if (!body || body.length > 4000) return;
    const id = selectedId; stopTyping(id); setDrafts((previous) => ({ ...previous, [id]: "" }));
    void submitPending({ id: crypto.randomUUID(), conversationId: id, text: body, createdAt: new Date().toISOString(), state: "sending" });
  }
  async function react(messageId: string, emoji: string, active: boolean) {
    const id = selectedRef.current;
    if (!id || revoked.current.has(id)) return;
    const message = await setReaction(id, messageId, emoji, active);
    if (alive.current) acceptMessages(id, [messageView(message, user.id)]);
  }
  function retry(clientId: string) { const item = pending.find((p) => p.id === clientId); if (item && item.state === "failed") void submitPending(item); }
  function opened(c: Conversation) { acceptConversation(c); setInboxStatus("ready"); select(c.id); }
  const pendingViews: PreviewMessage[] = pending.filter((p) => p.conversationId === selectedId).map((p) => ({ id: p.id, clientId: p.id, sender: profile(userRef.current), outgoing: true, kind: "text", text: p.text, createdAt: p.createdAt, timestamp: new Date(p.createdAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }), dateLabel: new Date(p.createdAt).toLocaleDateString([], { year: "numeric", month: "long", day: "numeric" }), state: p.state, failure: p.failure }));
  const messages = [...(currentThread?.messages ?? []), ...pendingViews.sort((a, b) => a.createdAt!.localeCompare(b.createdAt!))];
  return { conversations, selectedId, select, opened, groupChanges, revokeConversation, inboxStatus, inboxError, retryInbox: loadInbox, messages, historyLoading: !currentThread?.loaded, historyError: currentThread?.error, retryHistory: () => selectedId && void loadHistory(selectedId), connection, notice, retryConnection: () => { setNotice(""); void recoverDelivery(); void loadInbox(); if (selectedId) void loadHistory(selectedId); setReadTick((n) => n + 1); }, typing: selectedId ? (typing[selectedId] ?? []).map((t) => t.name).join(", ") : "", draft: selectedId ? drafts[selectedId] ?? "" : "", setDraft, send, retry, react, stopTyping, setAtBottom };
}
