import type { Conversation, Message } from "./api";

export function filterInbox(items: Conversation[], filter: "all" | "unread"): Conversation[] {
  return filter === "unread" ? items.filter((item) => item.unread_count > 0) : items;
}

export function shouldNotifyIncoming(message: Message, userId: string, activelyReading: boolean, live: boolean, seen: Set<string>): boolean {
  if (seen.has(message.id)) return false;
  seen.add(message.id);
  // Bound memory independently of the durable event cursor.
  if (seen.size > 1000) seen.delete(seen.values().next().value!);
  return live && !activelyReading && message.kind === "text" && message.sender !== null && message.sender.id !== userId;
}
