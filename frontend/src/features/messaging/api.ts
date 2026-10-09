import { apiRequest, ApiError, apiBaseUrl } from "@/lib/api";
import type { ConversationPreview, PreviewMessage, Profile, ReceiptStatus } from "./types";

export type User = { id: string; username: string | null; phone_e164: string | null; display_name: string; avatar_url: string | null; online: boolean; last_seen_at: string | null };
export type Session = { user: User; needs_profile: boolean };
export type Contact = { user: User; alias: string | null; presence: string };
export type Reaction = { user_id: string; emoji: string };
export type Message = { id: string; sequence: number; client_message_id: string | null; kind: "text" | "system"; body: string; created_at: string; sender: User | null; receipt: ReceiptStatus | null; reactions?: Reaction[]; reaction_version?: number };
export type Conversation = { id: string; kind: "direct" | "group"; title: string; avatar_url: string | null; other_user: User | null; last_activity_at: string; unread_count: number; latest_message: Message | null };

function object(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new ApiError("Unexpected API response");
  return value as Record<string, unknown>;
}
function string(value: unknown): string { if (typeof value !== "string") throw new ApiError("Unexpected API response"); return value; }
function optionalString(value: unknown): string | null { return value === null ? null : string(value); }
function integer(value: unknown): number { if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) throw new ApiError("Unexpected API response"); return value; }
function date(value: unknown): string { const result = string(value); if (!Number.isFinite(Date.parse(result))) throw new ApiError("Invalid API timestamp"); return result; }
function list<T>(value: unknown, parse: (entry: unknown) => T): T[] { if (!Array.isArray(value)) throw new ApiError("Unexpected API response"); return value.map(parse); }
function parseUser(value: unknown): User {
  const v = object(value);
  if (typeof v.online !== "boolean") throw new ApiError("Unexpected user presence");
  return { id: string(v.id), username: optionalString(v.username), phone_e164: optionalString(v.phone_e164), display_name: string(v.display_name), avatar_url: optionalString(v.avatar_url), online: v.online, last_seen_at: v.last_seen_at === null ? null : date(v.last_seen_at) };
}
function parseSession(value: unknown): Session {
  const v = object(value);
  if (typeof v.needs_profile !== "boolean") throw new ApiError("Unexpected API response");
  return { user: parseUser(v.user), needs_profile: v.needs_profile };
}
export function parseMessage(value: unknown): Message {
  const v = object(value);
  if (v.kind !== "text" && v.kind !== "system") throw new ApiError("Unexpected message type");
  if (v.receipt !== null && v.receipt !== "sent" && v.receipt !== "delivered" && v.receipt !== "read") throw new ApiError("Unexpected receipt");
  return { id: string(v.id), sequence: integer(v.sequence), client_message_id: optionalString(v.client_message_id), kind: v.kind, body: string(v.body), created_at: date(v.created_at), sender: v.sender === null ? null : parseUser(v.sender), receipt: v.receipt, reaction_version: v.reaction_version === undefined ? 0 : integer(v.reaction_version), reactions: v.reactions === undefined ? [] : list(v.reactions, (entry) => { const r = object(entry); return { user_id: string(r.user_id), emoji: string(r.emoji) }; }) };
}
export function parseConversation(value: unknown): Conversation {
  const v = object(value);
  if (v.kind !== "direct" && v.kind !== "group") throw new ApiError("Unexpected conversation type");
  return { id: string(v.id), kind: v.kind, title: string(v.title), avatar_url: optionalString(v.avatar_url), other_user: v.other_user === null ? null : parseUser(v.other_user), last_activity_at: date(v.last_activity_at), unread_count: integer(v.unread_count), latest_message: v.latest_message === null ? null : parseMessage(v.latest_message) };
}
const path = "/api/v1";
const json = (body: object, method = "POST"): RequestInit => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const restoreSession = (signal?: AbortSignal) => apiRequest(`${path}/auth/session`, parseSession, { signal });
export const challenge = (identifier: string) => apiRequest(`${path}/auth/challenges`, (value) => { const v = object(value); return { identifier: string(v.identifier), mock_code: string(v.mock_code), message: string(v.message) }; }, json({ identifier }));
export const signIn = (identifier: string, otp: string) => apiRequest(`${path}/auth/verify`, parseSession, json({ identifier, otp }));
export const saveProfile = (display_name: string, avatar_url: string) => apiRequest(`${path}/me`, parseSession, json({ display_name, avatar_url }, "PATCH"));
export const signOut = () => apiRequest(`${path}/auth/logout`, (value) => { if (object(value).ok !== true) throw new ApiError("Logout failed"); return true; }, json({}));
export const getInbox = (signal?: AbortSignal) => apiRequest(`${path}/conversations`, (value) => list(value, parseConversation), { signal });
export const getContacts = (query: string, signal?: AbortSignal) => apiRequest(`${path}/contacts?query=${encodeURIComponent(query)}`, (value) => list(value, (entry): Contact => { const v = object(entry); return { user: parseUser(v.user), alias: optionalString(v.alias), presence: string(v.presence) }; }), { signal });
export const findUsers = (query: string, signal?: AbortSignal) => apiRequest(`${path}/users?query=${encodeURIComponent(query)}`, (value) => list(value, parseUser), { signal });
export const addContact = (contact_user_id: string, alias?: string) => apiRequest(`${path}/contacts`, (value) => parseUser(object(value).user), json({ contact_user_id, ...(alias?.trim() ? { alias: alias.trim() } : {}) }));
export const openDirect = (contact_user_id: string) => apiRequest(`${path}/conversations/direct`, parseConversation, json({ contact_user_id }));

export type GroupMember = { user: User; role: "admin" | "member"; joined_at: string };
export type Group = { conversation: Conversation; members: GroupMember[]; my_role: "admin" | "member" };
function role(value: unknown): "admin" | "member" { if (value !== "admin" && value !== "member") throw new ApiError("Invalid member role"); return value; }
function parseGroup(value: unknown): Group {
  const v = object(value);
  return { conversation: parseConversation(v.conversation), my_role: role(v.my_role), members: list(v.members, (entry) => { const m = object(entry); return { user: parseUser(m.user), role: role(m.role), joined_at: date(m.joined_at) }; }) };
}
export const createGroup = (client_group_id: string, title: string, member_ids: string[]) => apiRequest(`${path}/groups`, parseGroup, json({ client_group_id, title, member_ids }));
export const getGroup = (id: string, signal?: AbortSignal) => apiRequest(`${path}/groups/${encodeURIComponent(id)}`, parseGroup, { signal });
export const renameGroup = (id: string, title: string) => apiRequest(`${path}/groups/${encodeURIComponent(id)}`, parseGroup, json({ title }, "PATCH"));
export const addGroupMembers = (id: string, member_ids: string[]) => apiRequest(`${path}/groups/${encodeURIComponent(id)}/members`, parseGroup, json({ member_ids }));
export const setGroupRole = (id: string, uid: string, role: "admin" | "member") => apiRequest(`${path}/groups/${encodeURIComponent(id)}/members/${encodeURIComponent(uid)}`, parseGroup, json({ role }, "PATCH"));
export const removeGroupMember = (id: string, uid: string) => apiRequest(`${path}/groups/${encodeURIComponent(id)}/members/${encodeURIComponent(uid)}`, parseGroup, { method: "DELETE" });
export const leaveGroup = (id: string) => apiRequest(`${path}/groups/${encodeURIComponent(id)}/leave`, (v) => { if (object(v).ok !== true) throw new ApiError("Could not leave group"); return true as const; }, json({}));

// Read persisted pages, honoring cancellation. Live records are merged separately.
export async function getHistory(id: string, currentUser: string, signal?: AbortSignal): Promise<PreviewMessage[]> {
  let cursor: number | null = null;
  let messages: Message[] = [];
  do {
    const page: { items: Message[]; next_cursor: number | null } = await apiRequest(`${path}/conversations/${encodeURIComponent(id)}/messages?limit=100${cursor === null ? "" : `&before_sequence=${cursor}`}`, (value) => {
      const v = object(value);
      return { items: list(v.items, parseMessage), next_cursor: v.next_cursor === null ? null : integer(v.next_cursor) };
    }, { signal });
    if (page.next_cursor !== null && (page.next_cursor === 0 || (cursor !== null && page.next_cursor >= cursor))) throw new ApiError("Invalid history cursor");
    messages = [...page.items, ...messages];
    cursor = page.next_cursor;
  } while (cursor !== null);
  return messages.map((m) => messageView(m, currentUser));
}
export function messageView(m: Message, currentUser: string): PreviewMessage {
  return { id: m.id, clientId: m.client_message_id ?? undefined, sequence: m.sequence, createdAt: m.created_at, kind: m.kind, sender: m.sender ? profile(m.sender) : { id: "system", name: "System" }, outgoing: m.sender?.id === currentUser,
    text: m.body, timestamp: new Date(m.created_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }), dateLabel: new Date(m.created_at).toLocaleDateString([], { year: "numeric", month: "long", day: "numeric" }), receipt: m.receipt ?? undefined, reactions: m.reactions ?? [], reactionVersion: m.reaction_version ?? 0 };
}
export const sendMessage = (id: string, client_message_id: string, body: string) => apiRequest(`${path}/conversations/${encodeURIComponent(id)}/messages`, parseMessage, json({ client_message_id, body }));
export const setReaction = (id: string, messageId: string, emoji: string, active: boolean) => apiRequest(`${path}/conversations/${encodeURIComponent(id)}/messages/${encodeURIComponent(messageId)}/reactions`, parseMessage, json({ emoji, active }));
export const markRead = (id: string, through_sequence: number) => apiRequest(`${path}/conversations/${encodeURIComponent(id)}/read`, parseConversation, json({ through_sequence }));
export const markDelivered = (id: string, message_ids: string[]) => apiRequest(`${path}/conversations/${encodeURIComponent(id)}/delivered`, (v) => { if (object(v).ok !== true) throw new ApiError("Acknowledgement failed"); return true; }, json({ message_ids }));
export const pendingDelivery = () => apiRequest(`${path}/messages/pending-delivery`, (v) => list(v, (entry) => { const row = object(entry); return { conversation_id: string(row.conversation_id), message_ids: list(row.message_ids, string) }; }));
export function websocketUrl(cursor: number): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  const url = new URL(configured || `${apiBaseUrl()}/api/v1/ws`);
  if (!configured) url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  if (!["ws:", "wss:"].includes(url.protocol)) throw new ApiError("WebSocket URL must use WS or WSS");
  url.searchParams.set("cursor", String(cursor));
  return url.toString();
}
export type LiveEvent = { type: string; eventId?: number; conversation?: Conversation; messages?: Message[]; userId?: string; online?: boolean; lastSeen?: string | null; conversationId?: string; name?: string; typing?: boolean; expires?: number; cursor?: number; error?: string };
export function parseLiveEvent(value: unknown): LiveEvent {
  const e = object(value), p = object(e.payload), type = string(e.type);
  const common = { type, eventId: e.event_id === undefined ? undefined : integer(e.event_id) };
  if (["message.created", "message.receipt_updated", "message.reactions_updated", "conversation.updated", "group.created", "group.members_updated"].includes(type)) return { ...common, conversation: parseConversation(p.conversation), messages: list(p.messages, parseMessage) };
  if (type === "conversation.access_revoked") return { ...common, conversationId: string(p.conversation_id) };
  if (type === "presence.updated") { if (typeof p.online !== "boolean") throw new ApiError("Invalid presence event"); return { ...common, userId: string(p.user_id), online: p.online, lastSeen: p.last_seen_at === null ? null : date(p.last_seen_at) }; }
  if (type === "typing.updated") { if (typeof p.is_typing !== "boolean") throw new ApiError("Invalid typing event"); return { ...common, userId: string(p.user_id), conversationId: string(e.conversation_id), name: string(p.name), typing: p.is_typing, expires: Date.parse(date(p.expires_at)) }; }
  if (type === "session.ready" || type === "sync.required") return { ...common, userId: p.user_id === undefined ? undefined : string(p.user_id), cursor: integer(p.cursor) };
  return { ...common, error: type === "error" ? string(p.message) : undefined };
}
export function presence(user: User): string { return user.online ? "Online" : user.last_seen_at ? `Last seen ${new Date(user.last_seen_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}` : "Offline"; }
export function profile(user: User): Profile { return { id: user.id, name: user.display_name, avatar: user.avatar_url ?? undefined, color: "#4278a3" }; }
export function conversationView(c: Conversation, userId: string, messages: PreviewMessage[] = []): ConversationPreview {
  const latest = c.latest_message;
  const prefix = latest?.sender?.id === userId ? "You: " : c.kind === "group" && latest?.sender ? `${latest.sender.display_name}: ` : "";
  return { id: c.id, kind: c.kind, profile: { id: c.id, name: c.title, avatar: c.avatar_url ?? undefined }, preview: latest ? `${prefix}${latest.body}` : "No messages yet",
    activity: new Date(c.last_activity_at).toDateString() === new Date().toDateString() ? new Date(c.last_activity_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : new Date(c.last_activity_at).toLocaleDateString([], { month: "short", day: "numeric" }), unread: c.unread_count, receipt: latest?.receipt ?? undefined, bubbleColor: c.kind === "group" ? "#c83c43" : "#2867f5", messages, presence: c.other_user ? presence(c.other_user) : undefined };
}
export function errorMessage(error: unknown): string { return error instanceof ApiError ? error.message : "Could not reach the API. Check the backend connection and retry."; }
