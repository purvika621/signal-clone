"use client";
import { useEffect, useRef, useState } from "react";
import { Avatar } from "@/components/ui/avatar";
import { addGroupMembers, errorMessage, getContacts, getGroup, leaveGroup, profile, removeGroupMember, renameGroup, setGroupRole, type Contact, type Group } from "@/features/messaging/api";
import styles from "./groups.module.css";
import { useToasts } from "@/components/ui/toasts";

export function GroupDetails({ id, userId, revision, onClose, onLeave }: { id: string; userId: string; revision: number; onClose: () => void; onLeave: () => void }) {
  const { notify } = useToasts();
  const [success, setSuccess] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const [group, setGroup] = useState<Group | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const generation = useRef(0);
  const alive = useRef(true);
  const [attempt, setAttempt] = useState(0);
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [confirmation, setConfirmation] = useState<{ kind: "leave" | "remove" | "role"; uid?: string; name?: string; role?: "admin" | "member" } | null>(null);
  useEffect(() => {
    const element = dialog.current!; element.showModal(); alive.current = true;
    return () => { alive.current = false; element.close(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController(), current = ++generation.current;
    getGroup(id, controller.signal).then((value) => { if (!controller.signal.aborted && current === generation.current) { setGroup(value); setTitle(value.conversation.title); setError(""); } }).catch((e) => { if (!controller.signal.aborted && current === generation.current) setError(errorMessage(e)); });
    return () => controller.abort();
  }, [id, revision, attempt]);
  async function command(action: () => Promise<Group | true>) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError("");
    setSuccess("");
    // Invalidate old detail fetches; socket changes trigger another authoritative fetch.
    ++generation.current;
    try {
      const value = await action();
      notify({ title: value === true ? "Left group" : "Group updated" });
      if (!alive.current) return;
      if (value === true) { onLeave(); onClose(); return; }
      setConfirmation(null); setAdding(false); setSelected([]);
      setSuccess("Group changes saved.");
      // Fetch the latest roster instead of letting a delayed command response
      // overwrite a newer membership event from another admin.
      setAttempt((n) => n + 1);
    } catch (e) { if (alive.current) setError(errorMessage(e)); }
    finally { busyRef.current = false; if (alive.current) setBusy(false); }
  }
  async function showAdd() {
    setAdding(true); setContacts(null); setError(""); setQuery(""); setSelected([]);
    try { const items = await getContacts(""); if (alive.current) setContacts(items); }
    catch (e) { if (alive.current) setError(errorMessage(e)); }
  }
  const admin = group?.my_role === "admin";
  const available = contacts?.filter((c) => !group?.members.some((m) => m.user.id === c.user.id) && `${c.alias ?? ""} ${c.user.display_name} ${c.user.username ?? ""}`.toLowerCase().includes(query.toLowerCase()));
  function confirm() {
    if (!confirmation) return;
    if (confirmation.kind === "leave") void command(() => leaveGroup(id));
    else if (confirmation.kind === "remove") void command(() => removeGroupMember(id, confirmation.uid!));
    else void command(() => setGroupRole(id, confirmation.uid!, confirmation.role!));
  }
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby="group-details-title" onCancel={(e) => { if (busy) e.preventDefault(); else if (confirmation) { e.preventDefault(); setConfirmation(null); } else if (adding) { e.preventDefault(); setAdding(false); } else onClose(); }}><div className={styles.content}>
    <header className={styles.heading}><h2 id="group-details-title">Group details</h2><button type="button" disabled={busy} aria-label="Close group details" onClick={onClose}>Close</button></header>
    {error && <div className={styles.error} role="alert">{error}<button type="button" disabled={busy} onClick={() => adding && contacts === null ? void showAdd() : setAttempt((n) => n + 1)}>Retry loading</button></div>}
    {success && <p role="status">{success}</p>}
    {!group && !error && <p role="status">Loading group…</p>}
    {group && <>
      <div className={styles.heading}><Avatar profile={{ id, name: group.conversation.title, avatar: group.conversation.avatar_url ?? undefined }} size={56} /><h2>{group.conversation.title}</h2></div>
      <p className={styles.muted}>{group.members.length} members · {admin ? "You are an admin" : "You are a member"}</p>
      {admin && <form className={styles.actions} onSubmit={(e) => { e.preventDefault(); void command(() => renameGroup(id, title.trim())); }}><label>Group name<input required maxLength={100} disabled={busy} value={title} onChange={(e) => setTitle(e.target.value)} /></label><button type="submit" disabled={busy || !title.trim() || title.trim() === group.conversation.title}>Save name</button></form>}
      <section aria-label="Group members"><h3>Members</h3><ul className={styles.memberList}>{group.members.map((member) => <li className={styles.row} key={member.user.id}><Avatar profile={profile(member.user)} size={36} /><span className={styles.identity}><strong>{member.user.display_name}{member.user.id === userId ? " (You)" : ""}</strong><small>{member.user.username ? `@${member.user.username}` : member.user.phone_e164}</small></span>{member.role === "admin" && <span className={styles.role}>Admin</span>}{admin && <div className={styles.actions}><button type="button" disabled={busy} onClick={() => setConfirmation({ kind: "role", uid: member.user.id, name: member.user.display_name, role: member.role === "admin" ? "member" : "admin" })}>{member.role === "admin" ? "Remove admin" : "Make admin"}</button>{member.user.id !== userId && <button className={styles.danger} type="button" disabled={busy} onClick={() => setConfirmation({ kind: "remove", uid: member.user.id, name: member.user.display_name })}>Remove</button>}</div>}</li>)}</ul></section>
      {admin && !adding && <button type="button" disabled={busy} onClick={() => void showAdd()}>Add members</button>}
      {admin && adding && <section aria-label="Add group members"><label>Search contacts<input value={query} disabled={busy} onChange={(e) => setQuery(e.target.value)} /></label>{contacts === null && !error && <p role="status">Loading contacts…</p>}<ul className={styles.memberList}>{available?.map((contact) => <li className={styles.row} key={contact.user.id}><Avatar profile={profile(contact.user)} size={32} /><span className={styles.identity}>{contact.alias || contact.user.display_name}</span><button type="button" disabled={busy} aria-pressed={selected.includes(contact.user.id)} onClick={() => setSelected((ids) => ids.includes(contact.user.id) ? ids.filter((uid) => uid !== contact.user.id) : [...ids, contact.user.id])}>{selected.includes(contact.user.id) ? "Selected" : "Select"}</button></li>)}</ul>{available?.length === 0 && <p className={styles.muted}>No available contacts.</p>}<div className={styles.actions}><button className={styles.primary} type="button" disabled={busy || !selected.length} onClick={() => void command(() => addGroupMembers(id, selected))}>Add {selected.length || ""} members</button><button type="button" disabled={busy} onClick={() => setAdding(false)}>Cancel</button></div></section>}
      <button type="button" className={styles.danger} disabled={busy} onClick={() => setConfirmation({ kind: "leave" })}>Leave group</button>
      {confirmation && <div className={styles.confirmation} role="alert"><p>{confirmation.kind === "leave" ? "Leave this group? You will lose access to its messages. The last admin must make another member an admin first." : confirmation.kind === "remove" ? `Remove ${confirmation.name}? They will lose access immediately.` : `Make ${confirmation.name} ${confirmation.role === "admin" ? "an admin" : "a regular member"}?`}</p><div className={styles.actions}><button type="button" className={styles.danger} disabled={busy} onClick={confirm}>Confirm</button><button type="button" disabled={busy} onClick={() => setConfirmation(null)}>Cancel</button></div></div>}
      {busy && <p role="status">Saving group changes…</p>}
    </>}
  </div></dialog>;
}
