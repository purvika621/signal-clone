"use client";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { conversationView, profile, type Conversation, type Message, type User } from "@/features/messaging/api";
import { filterInbox } from "@/features/messaging/notifications";
import { useMessaging } from "@/features/messaging/use-messaging";
import { useToasts } from "@/components/ui/toasts";
import { NavigationRail } from "./navigation-rail";
import { ConversationSidebar } from "./conversation-sidebar";
import { ConversationPane, EmptyConversation } from "./conversation-pane";
import { ContactPicker } from "./contact-picker";
import { GroupDetails } from "./group-details";
import { ContactDetailsDialog, SettingsDialog, type Destination } from "./settings-dialog";
import styles from "./workspace.module.css";

const mobileQuery = "(max-width: 640px)";
function subscribeMobile(callback: () => void) {
  const media = window.matchMedia(mobileQuery); media.addEventListener("change", callback);
  return () => media.removeEventListener("change", callback);
}
function isMobile() { return window.matchMedia(mobileQuery).matches; }

export function SignalWorkspace({ user, onProfile, readingPaused = false }: { user: User; onProfile: () => void; readingPaused?: boolean }) {
  const { notify, dismissConversation } = useToasts();
  const mobile = useSyncExternalStore(subscribeMobile, isMobile, () => false);
  const [mobileList, setMobileList] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [picker, setPicker] = useState<"chat" | "group" | null>(null);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [contactDetails, setContactDetails] = useState(false);
  const [destination, setDestination] = useState<Destination | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [focusSearch, setFocusSearch] = useState(0);
  const openFromToast = useRef<(id: string) => void>(() => {});
  const incoming = useCallback((conversation: Conversation, message: Message) => {
    notify({ title: conversation.title, body: `${conversation.kind === "group" ? `${message.sender?.display_name}: ` : ""}${message.body}`, conversationId: conversation.id, action: () => openFromToast.current(conversation.id) });
  }, [notify]);
  const chat = useMessaging(user, incoming, !readingPaused && !(mobile && mobileList) && !picker && !detailsId && !contactDetails && !destination);
  const selected = chat.conversations.find((c) => c.id === chat.selectedId);
  useEffect(() => {
    openFromToast.current = (id) => {
      if (!chat.conversations.some((c) => c.id === id)) return;
      setMobileList(false); setDestination(null); setDetailsId(null); setContactDetails(false); setPicker(null); setFilter("all"); setQuery(""); chat.select(id); dismissConversation(id);
    };
  }, [chat, dismissConversation]);
  function select(id: string) { setMobileList(false); setDetailsId(null); setContactDetails(false); chat.select(id); dismissConversation(id); }
  function opened(c: Conversation) { setMobileList(false); chat.opened(c); setPicker(null); setQuery(""); setFilter("all"); }
  function clearSelection() { setPicker(null); setDetailsId(null); setContactDetails(false); setDestination(null); chat.select(null); }
  function compose(mode: "chat" | "group") { setDestination(null); setDetailsId(null); setContactDetails(false); setPicker(mode); }
  useEffect(() => { if (focusSearch) searchRef.current?.focus(); }, [focusSearch]);
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || event.isComposing || event.keyCode === 229 || event.repeat) return;
      // Native dialog cancellation and the menu handler own Escape when present.
      if (document.querySelector("dialog[open]")) return;
      if (event.key === "Escape") {
        if (document.querySelector("[data-action-menu]")) return;
        if (picker) { event.preventDefault(); setPicker(null); }
        return;
      }
      const target = event.target instanceof Element ? event.target : null;
      if (target?.closest('[contenteditable="true"], input:not([type="search"]), textarea:not([data-message-composer])')) return;
      if (!(event.ctrlKey || event.metaKey) || event.altKey || readingPaused) return;
      if (event.key.toLowerCase() === "k" && !event.shiftKey) {
        event.preventDefault(); setMobileList(true); setPicker(null); setFocusSearch((value) => value + 1);
      } else if (event.key.toLowerCase() === "n" && event.shiftKey && !picker) {
        event.preventDefault(); compose("chat");
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, [picker, readingPaused]);
  return <main className={`${styles.workspace} ${selected && !picker && !mobileList ? styles.mobileChat : ""}`} data-signal-workspace="true" aria-label="Signal Desktop messaging workspace">
    <NavigationRail user={profile(user)} unread={chat.conversations.filter((c) => c.unread_count > 0).length} onClearSelection={clearSelection} onProfile={onProfile} onDestination={setDestination} onNewChat={() => compose("chat")} onNewGroup={() => compose("group")} />
    {picker ? <ContactPicker key={picker} initialGroup={picker === "group"} onBack={() => setPicker(null)} onOpen={opened} connection={chat.connection} notice={chat.notice} onRecover={chat.retryConnection} /> : <ConversationSidebar searchRef={searchRef} conversations={filterInbox(chat.conversations, filter).map((c) => conversationView(c, user.id))} selectedId={chat.selectedId} query={query} onSearch={setQuery} filter={filter} onFilter={setFilter} onSelect={select} onNewChat={() => compose("chat")} onNewGroup={() => compose("group")} onSettings={() => setDestination("Settings")} loading={chat.inboxStatus === "loading"} error={chat.inboxStatus === "error" ? chat.inboxError : undefined} onRetry={chat.retryInbox} connection={chat.connection} notice={chat.notice} onRecover={chat.retryConnection} />}
    {selected ? <ConversationPane currentUserId={user.id} onReact={chat.react} onBack={() => { chat.stopTyping(); setMobileList(true); }} key={selected.id} conversation={conversationView(selected, user.id, chat.messages)} loading={chat.historyLoading} error={chat.historyError} onRetry={chat.retryHistory} draft={chat.draft} onDraft={chat.setDraft} onSend={chat.send} onRetrySend={chat.retry} onBlur={chat.stopTyping} typing={chat.typing} onAtBottom={chat.setAtBottom} onGroupDetails={() => setDetailsId(selected.id)} onDetails={() => setContactDetails(true)} onCalls={() => setDestination("Calls")} /> : <EmptyConversation />}
    {detailsId && detailsId === selected?.id && selected.kind === "group" && <GroupDetails key={detailsId} id={detailsId} userId={user.id} revision={chat.groupChanges[detailsId] ?? 0} onClose={() => setDetailsId(null)} onLeave={() => { chat.revokeConversation(detailsId); setDetailsId(null); }} />}
    {contactDetails && selected?.other_user && <ContactDetailsDialog user={selected.other_user} onClose={() => setContactDetails(false)} />}
    {destination && <SettingsDialog key={destination} destination={destination} onClose={() => setDestination(null)} />}
  </main>;
}
