"use client";
import { useEffect, useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { Icon } from "@/components/ui/icon";
import { IconButton } from "@/components/ui/icon-button";
import { addContact, errorMessage, findUsers, getContacts, openDirect, presence, profile, type Contact, type Conversation, type User } from "@/features/messaging/api";
import styles from "./workspace.module.css";
import formStyles from "./onboarding.module.css";
import { NewGroup } from "./new-group";
import { useToasts } from "@/components/ui/toasts";

export function ContactPicker({ onBack, onOpen, connection, notice, onRecover, initialGroup = false }: { onBack: () => void; onOpen: (conversation: Conversation) => void; connection: string; notice: string; onRecover: () => void; initialGroup?: boolean }) {
  const { notify } = useToasts();
  const [mode, setMode] = useState<"contacts" | "add">("contacts");
  const [query, setQuery] = useState("");
  const [alias, setAlias] = useState("");
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [result, setResult] = useState<{ key: string; error?: string } | null>(null);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [newGroup, setNewGroup] = useState(initialGroup);
  const key = `${mode}:${query}`;
  const loaded = result?.key === key;
  const error = loaded ? result.error : undefined;
  useEffect(() => {
    let active = true; const controller = new AbortController();
    const timer = setTimeout(() => {
      if (mode === "contacts") {
        getContacts(query, controller.signal).then((items) => { if (active) { setContacts(items); setResult({ key }); } }).catch((e) => { if (active) setResult({ key, error: errorMessage(e) }); });
      } else {
        const request = query.trim().length >= 2 ? findUsers(query.trim(), controller.signal) : Promise.resolve([]);
        request.then((items) => { if (active) { setUsers(items); setResult({ key }); } }).catch((e) => { if (active) setResult({ key, error: errorMessage(e) }); });
      }
    }, 180);
    return () => { active = false; clearTimeout(timer); controller.abort(); };
  }, [mode, query, attempt, key]);
  async function pick(user: User) {
    setBusy(true); setActionError("");
    try {
      if (mode === "add") {
        await addContact(user.id, alias);
        notify({ title: "Contact added", body: alias || user.display_name });
        setMode("contacts"); setQuery(""); setAlias(""); setResult(null);
      } else onOpen(await openDirect(user.id));
    } catch (e) { setActionError(errorMessage(e)); } finally { setBusy(false); }
  }
  const rows: Contact[] = mode === "contacts" ? contacts : users.map((user) => ({ user, alias: null, presence: presence(user) }));
  if (newGroup) return <NewGroup onBack={() => setNewGroup(false)} onOpen={onOpen} />;
  return <aside className={styles.sidebar} aria-label={mode === "contacts" ? "New chat" : "Add contact"}>
    <header className={`${styles.sidebarHeader} ${styles.pickerHeader}`}><IconButton icon="back" label="Back to chats" onClick={onBack} /><h1>{mode === "contacts" ? "New chat" : "Add contact"}</h1></header>
    {(connection !== "Connected" || notice) && <div className={styles.connectionStatus} role="status">{notice || connection}{notice && <button type="button" onClick={onRecover}>Retry</button>}</div>}
    <div className={styles.searchContainer}><div className={styles.searchField}><Icon name="search" size={19} /><input autoFocus type="search" aria-label="Search contacts" placeholder="Name, username, or number" maxLength={100} value={query} onChange={(e) => { setQuery(e.target.value); setActionError(""); }} /></div></div>
    <div className={styles.pickerTools}>{mode === "contacts" && <button type="button" disabled={busy} onClick={() => setNewGroup(true)}>New group</button>}<button type="button" disabled={busy} onClick={() => { setMode(mode === "contacts" ? "add" : "contacts"); setQuery(""); setResult(null); setActionError(""); }}>{mode === "contacts" ? "Add a contact" : "Back to contacts"}</button>{mode === "add" && <><p>Find a registered user. Type at least two characters.</p><label>Contact alias (optional)<input maxLength={100} value={alias} onChange={(e) => setAlias(e.target.value)} /></label></>}</div>
    <div className={styles.conversationList}>
      {actionError && <div className={formStyles.error} role="alert">{actionError}</div>}
      {!loaded && <p className={styles.noResults} role="status">Loading contacts…</p>}
      {error && <div className={formStyles.error} role="alert">{error}<button type="button" onClick={() => { setResult(null); setAttempt((v) => v + 1); }}>Retry</button></div>}
      {loaded && !error && <ul>{rows.map((contact) => <li key={contact.user.id}><button className={styles.conversationRow} disabled={busy} type="button" onClick={() => pick(contact.user)}><Avatar profile={profile(contact.user)} /><span className={styles.rowContent}><span className={styles.rowName}>{contact.alias || contact.user.display_name}</span><span className={styles.preview}>{contact.user.username ? `@${contact.user.username}` : contact.user.phone_e164}<br />{contact.presence}</span></span>{mode === "add" && <span>Add</span>}</button></li>)}</ul>}
      {loaded && !error && rows.length === 0 && <p className={styles.noResults} role="status">{mode === "add" && query.trim().length < 2 ? "Search for a registered user" : "No contacts found"}</p>}
      {busy && <p className={styles.noResults} role="status">{mode === "add" ? "Adding contact…" : "Opening conversation…"}</p>}
    </div>
  </aside>;
}
