import { Fragment, useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import type { ConversationPreview, PreviewMessage } from "@/features/messaging/types";
import { ActionMenu } from "@/components/ui/action-menu";
import { Receipt } from "./receipt";
import styles from "./workspace.module.css";

function ConversationHeader({ conversation, onGroupDetails, onDetails, onCalls }: { conversation: ConversationPreview; onGroupDetails?: () => void; onDetails: () => void; onCalls: () => void }) {
  return <header className={styles.chatHeader}>
    <div className={styles.chatIdentity}><Avatar profile={conversation.profile} size={34} /><div className={styles.headerText}><h2 title={conversation.profile.name}>{conversation.profile.name}</h2>{conversation.presence && <small className={styles.presence} title={conversation.presence}>{conversation.presence}</small>}</div></div>
    <div className={styles.headerActions}><IconButton icon="video" label="Video call" onClick={onCalls} />{conversation.kind === "direct" && <IconButton icon="phone" label="Voice call" onClick={onCalls} />}<IconButton icon="search" label="Search this conversation" unavailable /><ActionMenu label="Conversation menu" items={[{ label: conversation.kind === "group" ? "Group details" : "Contact details", action: conversation.kind === "group" ? onGroupDetails! : onDetails }, { label: "Calls (Coming Soon)", action: onCalls }]} /></div>
  </header>;
}

function MessageBubble({ message, group, grouped, onRetry }: { message: PreviewMessage; group: boolean; grouped: boolean; onRetry: (id: string) => void }) {
  return <div className={`${styles.messageRow} ${message.outgoing ? styles.outgoing : styles.incoming} ${grouped ? styles.grouped : ""}`}>
    {group && !message.outgoing && <span className={styles.senderAvatar}>{!grouped && <Avatar profile={message.sender} size={28} />}</span>}
    <div className={styles.bubble}>
      {group && !message.outgoing && !grouped && <span className={styles.senderName} style={{ color: message.sender.color }}>{message.sender.name}</span>}
      <p className={styles.messageText}>{message.text}<span className={`${styles.metadataSpace} ${message.state === "failed" ? styles.metadataFailed : message.receipt || message.state ? styles.metadataWithReceipt : ""}`} aria-hidden="true">{message.timestamp}</span></p>
      <span className={styles.messageMetadata}><time title={`${message.dateLabel}, ${message.timestamp}`}>{message.timestamp}</time>{message.state === "sending" ? <span title="Sending" aria-label="Sending"><Icon name="clock" size={12} /></span> : message.state === "failed" ? <button className={styles.retrySend} type="button" title={message.failure} aria-label={`Retry failed message: ${message.text}`} onClick={() => onRetry(message.clientId!)}>Failed · Retry</button> : message.receipt && <Receipt status={message.receipt} />}</span>
    </div>
  </div>;
}

type ComposerProps = { draft: string; onDraft: (value: string) => void; onSend: () => void; onBlur: () => void; disabled: boolean; typing: string };
function Composer({ draft, onDraft, onSend, onBlur, disabled, typing }: ComposerProps) {
  return <footer className={styles.composer} aria-label="Message composer">
    {typing && <div className={styles.typingLabel} role="status">{typing} {typing.includes(",") ? "are" : "is"} typing…</div>}
    <IconButton icon="smile" label="Emoji" unavailable size={26} />
    <div className={styles.composerField}><textarea rows={1} style={{ height: Math.min(3, draft.split("\n").length) * 24 }} maxLength={4000} placeholder="Message" aria-label="Message" disabled={disabled} value={draft} onChange={(e) => onDraft(e.target.value)} onBlur={onBlur} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (!disabled && draft.trim()) onSend(); } }} /></div>
    <div className={styles.composerActions}><IconButton icon="sticker" label="Stickers" unavailable size={25} /><button className={`signal-icon-button ${styles.sendButton}`} type="button" aria-label="Send message" title="Send message" disabled={disabled || !draft.trim()} onClick={onSend}><Icon name="send" size={24} /></button><IconButton icon="plus" label="Add attachment" unavailable size={26} /></div>
  </footer>;
}

export function ConversationPane({ conversation, loading, error, onRetry, draft, onDraft, onSend, onRetrySend, onBlur, typing, onAtBottom, onGroupDetails, onDetails, onCalls }: { conversation: ConversationPreview; loading: boolean; error?: string; onRetry: () => void; onRetrySend: (id: string) => void; onAtBottom: (value: boolean) => void; onGroupDetails?: () => void; onDetails: () => void; onCalls: () => void } & Omit<ComposerProps, "disabled">) {
  const threadRef = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const previousCount = useRef(0);
  useEffect(() => {
    const thread = threadRef.current;
    if (thread && (nearBottom.current || previousCount.current === 0 || conversation.messages.at(-1)?.state === "sending")) thread.scrollTop = thread.scrollHeight;
    previousCount.current = conversation.messages.length;
  }, [conversation.id, conversation.messages, loading]);
  const theme = { "--chat-color": conversation.bubbleColor } as CSSProperties;
  return <section className={styles.chatPane} aria-label={`${conversation.profile.name} conversation`} style={theme}>
    <ConversationHeader conversation={conversation} onGroupDetails={onGroupDetails} onDetails={onDetails} onCalls={onCalls} />
    <div ref={threadRef} className={styles.messageThread} role="region" aria-label="Message history" tabIndex={0} onScroll={(e) => { const t = e.currentTarget; nearBottom.current = t.scrollHeight - t.scrollTop - t.clientHeight < 80; onAtBottom(nearBottom.current); }}>
      {loading ? <p className={styles.noResults} role="status">Loading messages…</p> : error ? <div className={styles.noResults} role="alert"><p>{error}</p><button type="button" onClick={onRetry}>Retry</button></div> : <div className={styles.messages}>{conversation.messages.length === 0 && <p className={styles.noResults} role="status">No messages yet.</p>}{conversation.messages.map((message, index) => {
        const previous = conversation.messages[index - 1];
        const newDate = previous?.dateLabel !== message.dateLabel;
        const grouped = !newDate && previous?.sender.id === message.sender.id;
        return <Fragment key={message.id}>{newDate && <div className={styles.dateSeparator}>{message.dateLabel}</div>}{message.kind === "system" ? <div className={styles.dateSeparator}>{message.text}</div> : <MessageBubble message={message} group={conversation.kind === "group"} grouped={grouped} onRetry={onRetrySend} />}</Fragment>;
      })}</div>}
    </div>
    <Composer draft={draft} onDraft={onDraft} onSend={onSend} onBlur={onBlur} disabled={loading} typing={typing} />
  </section>;
}

export function EmptyConversation() {
  return <section className={styles.emptyPane} aria-label="No conversation selected"><div className={styles.emptyContent}><span className={styles.emptyIcon}><Icon name="chat" size={44} /></span><h2>Select a conversation</h2><p>Choose a chat from the list to view your messages.</p></div></section>;
}
