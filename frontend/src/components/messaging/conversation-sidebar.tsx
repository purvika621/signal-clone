import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { ConversationPreview } from "@/features/messaging/types";
import { Receipt } from "./receipt";
import styles from "./workspace.module.css";
import { ActionMenu } from "@/components/ui/action-menu";
import overlayStyles from "@/components/ui/overlays.module.css";

function ConversationRow({ conversation, selected, onSelect }: { conversation: ConversationPreview; selected: boolean; onSelect: () => void }) {
  return <li><button className={`${styles.conversationRow} ${selected ? styles.conversationSelected : ""}`} type="button" onClick={onSelect} aria-current={selected ? "true" : undefined} aria-label={`${conversation.profile.name}${conversation.kind === "group" ? ", group" : ""}${conversation.unread ? `, ${conversation.unread} unread messages` : ""}`}>
    <Avatar profile={conversation.profile} />
    <span className={styles.rowContent}>
      <span className={styles.rowHeading}><span className={styles.rowName}>{conversation.profile.name}</span><span className={styles.activity}>{conversation.activity}</span></span>
      <span className={styles.rowBottom}><span className={styles.preview}>{conversation.preview}</span><span className={styles.rowStatus}>{conversation.unread > 0 ? <span className={styles.unreadBadge}>{conversation.unread}</span> : conversation.receipt && <Receipt status={conversation.receipt} />}</span></span>
    </span>
  </button></li>;
}

export function ConversationSidebar({ conversations, selectedId, query, onSearch, onSelect, onNewChat, onNewGroup, onSettings, filter, onFilter, loading, error, onRetry, connection, notice, onRecover }: {
  conversations: ConversationPreview[]; selectedId: string | null; query: string; onSearch: (query: string) => void; onSelect: (id: string) => void;
  onNewChat: () => void; loading: boolean; error?: string; onRetry: () => void;
  connection: string; notice: string; onRecover: () => void;
  onNewGroup: () => void; onSettings: () => void; filter: "all" | "unread"; onFilter: (value: "all" | "unread") => void;
}) {
  const normalized = query.trim().toLocaleLowerCase();
  const visible = conversations.filter((conversation) => `${conversation.profile.name} ${conversation.preview}`.toLocaleLowerCase().includes(normalized));
  return <aside className={styles.sidebar} aria-label="Conversations">
    <header className={styles.sidebarHeader}><h1>Chats</h1><div className={styles.sidebarActions}><IconButton icon="compose" label="New chat" onClick={onNewChat} /><ActionMenu label="Chat list menu" items={[{ label: "New chat", action: onNewChat }, { label: "New group", action: onNewGroup }, { label: "All conversations", action: () => onFilter("all") }, { label: "Unread conversations", action: () => onFilter("unread") }, { label: "Settings", action: onSettings }]} /></div></header>
    {(connection !== "Connected" || notice) && <div className={styles.connectionStatus} role="status">{notice || connection}{notice && <button type="button" onClick={onRecover}>Retry</button>}</div>}
    <div className={styles.searchContainer}><div className={styles.searchField}><Icon name="search" size={19} /><input type="search" aria-label="Search conversations" placeholder="Search" value={query} onChange={(event) => onSearch(event.target.value)} autoComplete="off" />{query && <IconButton icon="close" label="Clear search" size={16} onClick={() => onSearch("")} />}</div></div>
    <div className={overlayStyles.filters} aria-label="Inbox filters"><button type="button" aria-pressed={filter === "all"} onClick={() => onFilter("all")}>All</button><button type="button" aria-pressed={filter === "unread"} onClick={() => onFilter("unread")}>Unread</button></div>
    <div className={styles.conversationList}>{loading ? <p className={styles.noResults} role="status">Loading conversations…</p> : error ? <div className={styles.noResults} role="alert"><p>{error}</p><button type="button" onClick={onRetry}>Retry</button></div> : <><ul>{visible.map((conversation) => <ConversationRow key={conversation.id} conversation={conversation} selected={selectedId === conversation.id} onSelect={() => onSelect(conversation.id)} />)}</ul>{visible.length === 0 && <p className={styles.noResults} role="status">{query ? "No conversations found" : filter === "unread" ? "No unread conversations" : "No conversations yet. Start a new chat."}</p>}</>}</div>
  </aside>;
}
