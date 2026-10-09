"use client";
import { useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { IconButton } from "@/components/ui/icon-button";
import { createGroup, errorMessage, getContacts, profile, type Contact, type Conversation } from "@/features/messaging/api";
import styles from "./workspace.module.css";
import groupStyles from "./groups.module.css";
import { useToasts } from "@/components/ui/toasts";

export function NewGroup({ onBack, onOpen }: { onBack: () => void; onOpen: (conversation: Conversation) => void }) {
  const { notify } = useToasts();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [step, setStep] = useState<"members" | "details">("members");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const intent = useRef<{ id: string; title: string; members: string[] } | null>(null);
  const submitting = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    getContacts("", controller.signal).then((items) => { if (!controller.signal.aborted) { setContacts(items); setLoaded(true); setError(""); } }).catch((e) => { if (!controller.signal.aborted) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [attempt]);
  async function create() {
    if (submitting.current || !title.trim() || selected.length === 0) return;
    submitting.current = true; setBusy(true); setError("");
    intent.current ??= { id: crypto.randomUUID(), title: title.trim(), members: [...selected] };
    const request = intent.current; setAttempted(true);
    try { const group = await createGroup(request.id, request.title, request.members); notify({ title: "Group created", body: group.conversation.title }); onOpen(group.conversation); }
    catch (e) { setError(errorMessage(e)); }
    finally { submitting.current = false; setBusy(false); }
  }
  const results = contacts.filter((c) => `${c.alias ?? ""} ${c.user.display_name} ${c.user.username ?? ""} ${c.user.phone_e164 ?? ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <aside className={styles.sidebar} aria-label="Create group">
    <header className={`${styles.sidebarHeader} ${styles.pickerHeader}`}><IconButton icon="back" label="Back" unavailable={busy} onClick={() => step === "details" && !intent.current ? setStep("members") : onBack()} /><h1>New group</h1></header>
    {step === "members" ? <>
      <div className={styles.searchContainer}><div className={styles.searchField}><input autoFocus type="search" placeholder="Search contacts" aria-label="Search group contacts" value={query} onChange={(e) => setQuery(e.target.value)} /></div></div>
      <div className={groupStyles.stepActions}><p>{selected.length} selected · You will be the admin</p><button type="button" className={groupStyles.primary} disabled={!selected.length || !loaded} onClick={() => { setStep("details"); setError(""); }}>Next</button></div>
      <div className={styles.conversationList}>{!loaded && !error && <p className={styles.noResults}>Loading contacts…</p>}{loaded && <ul>{results.map((contact) => <li key={contact.user.id}><button type="button" className={styles.conversationRow} aria-pressed={selected.includes(contact.user.id)} onClick={() => setSelected((ids) => ids.includes(contact.user.id) ? ids.filter((id) => id !== contact.user.id) : [...ids, contact.user.id])}><Avatar profile={profile(contact.user)} /><span className={styles.rowContent}><span className={styles.rowName}>{contact.alias || contact.user.display_name}</span><span className={styles.preview}>{contact.user.username ? `@${contact.user.username}` : contact.user.phone_e164}</span></span><span className={groupStyles.selection} aria-hidden="true">{selected.includes(contact.user.id) ? "✓" : ""}</span></button></li>)}</ul>}{loaded && results.length === 0 && <p className={styles.noResults}>No contacts found</p>}</div>
    </> : <div className={groupStyles.stepActions}><Avatar profile={{ id: "new-group", name: title || "Group" }} size={72} /><form onSubmit={(e) => { e.preventDefault(); void create(); }}><label>Group name<input autoFocus required maxLength={100} disabled={attempted} value={title} onChange={(e) => setTitle(e.target.value)} /></label><p>Members: You, {contacts.filter((c) => selected.includes(c.user.id)).map((c) => c.alias || c.user.display_name).join(", ")}</p><button type="submit" className={groupStyles.primary} disabled={busy || !title.trim()}>{busy ? "Creating…" : attempted ? "Retry creation" : "Create group"}</button></form>{attempted && <p>Retries use the same request and details to prevent duplicate groups.</p>}</div>}
    {error && <div className={groupStyles.error} role="alert">{error}{!loaded && <button type="button" onClick={() => setAttempt((n) => n + 1)}>Retry contacts</button>}</div>}
  </aside>;
}
