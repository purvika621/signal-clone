"use client";
import { useCallback, useEffect, useRef, useState } from "react";
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

export function SignalWorkspace({ user, onProfile, readingPaused = false }: { user: User; onProfile: () => void; readingPaused?: boolean }) {
  const { notify, dismissConversation } = useToasts();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [picker, setPicker] = useState<"chat" | "group" | null>(null);
  const [detailsId, setDetailsId] = useState<string | null>(null);
  const [contactDetails, setContactDetails] = useState(false);
  const [destination, setDestination] = useState<Destination | null>(null);
  const openFromToast = useRef<(id: string) => void>(() => {});
  const incoming = useCallback((conversation: Conversation, message: Message) => {
    notify({ title: conversation.title, body: `${conversation.kind === "group" ? `${message.sender?.display_name}: ` : ""}${message.body}`, conversationId: conversation.id, action: () => openFromToast.current(conversation.id) });
  }, [notify]);
  const chat = useMessaging(user, incoming, !readingPaused && !picker && !detailsId && !contactDetails && !destination);
  const selected = chat.conversations.find((c) => c.id === chat.selectedId);
  useEffect(() => {
    openFromToast.current = (id) => {
      if (!chat.conversations.some((c) => c.id === id)) return;
      setDestination(null); setDetailsId(null); setContactDetails(false); setPicker(null); setFilter("all"); setQuery(""); chat.select(id); dismissConversation(id);
    };
  }, [chat, dismissConversation]);
  function select(id: string) { setDetailsId(null); setContactDetails(false); chat.select(id); dismissConversation(id); }
  function opened(c: Conversation) { chat.opened(c); setPicker(null); setQuery(""); setFilter("all"); }
  function clearSelection() { setPicker(null); setDetailsId(null); setContactDetails(false); setDestination(null); chat.select(null); }
  function compose(mode: "chat" | "group") { setDestination(null); setDetailsId(null); setContactDetails(false); setPicker(mode); }
  return <main className={styles.workspace} data-signal-workspace="true" aria-label="Signal Desktop messaging workspace">
    <NavigationRail user={profile(user)} unread={chat.conversations.filter((c) => c.unread_count > 0).length} onClearSelection={clearSelection} onProfile={onProfile} onDestination={setDestination} onNewChat={() => compose("chat")} onNewGroup={() => compose("group")} />
    {picker ? <ContactPicker key={picker} initialGroup={picker === "group"} onBack={() => setPicker(null)} onOpen={opened} connection={chat.connection} notice={chat.notice} onRecover={chat.retryConnection} /> : <ConversationSidebar conversations={filterInbox(chat.conversations, filter).map((c) => conversationView(c, user.id))} selectedId={chat.selectedId} query={query} onSearch={setQuery} filter={filter} onFilter={setFilter} onSelect={select} onNewChat={() => compose("chat")} onNewGroup={() => compose("group")} onSettings={() => setDestination("Settings")} loading={chat.inboxStatus === "loading"} error={chat.inboxStatus === "error" ? chat.inboxError : undefined} onRetry={chat.retryInbox} connection={chat.connection} notice={chat.notice} onRecover={chat.retryConnection} />}
    {selected ? <ConversationPane key={selected.id} conversation={conversationView(selected, user.id, chat.messages)} loading={chat.historyLoading} error={chat.historyError} onRetry={chat.retryHistory} draft={chat.draft} onDraft={chat.setDraft} onSend={chat.send} onRetrySend={chat.retry} onBlur={chat.stopTyping} typing={chat.typing} onAtBottom={chat.setAtBottom} onGroupDetails={() => setDetailsId(selected.id)} onDetails={() => setContactDetails(true)} onCalls={() => setDestination("Calls")} /> : <EmptyConversation />}
    {detailsId && detailsId === selected?.id && selected.kind === "group" && <GroupDetails key={detailsId} id={detailsId} userId={user.id} revision={chat.groupChanges[detailsId] ?? 0} onClose={() => setDetailsId(null)} onLeave={() => { chat.revokeConversation(detailsId); setDetailsId(null); }} />}
    {contactDetails && selected?.other_user && <ContactDetailsDialog user={selected.other_user} onClose={() => setContactDetails(false)} />}
    {destination && <SettingsDialog key={destination} destination={destination} onClose={() => setDestination(null)} />}
  </main>;
}
