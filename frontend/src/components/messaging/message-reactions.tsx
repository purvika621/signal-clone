"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/ui/icon";
import { errorMessage } from "@/features/messaging/api";
import type { PreviewMessage } from "@/features/messaging/types";
import styles from "./workspace.module.css";

const emojis = ["❤️", "😂", "👍", "😮", "😢", "🎉"];
export function MessageReactions({ message, currentUserId, onReact }: { message: PreviewMessage; currentUserId: string; onReact: (id: string, emoji: string, active: boolean) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLButtonElement>("[data-reaction-choice]")?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !event.defaultPrevented && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault(); event.stopImmediatePropagation(); setOpen(false); trigger.current?.focus();
      }
    };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [open]);
  const reactions = message.reactions ?? [];
  const mine = (emoji: string) => reactions.some((r) => r.emoji === emoji && r.user_id === currentUserId);
  async function toggle(emoji: string) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError("");
    try { await onReact(message.id, emoji, !mine(emoji)); setOpen(false); trigger.current?.focus(); }
    catch (e) { setError(errorMessage(e)); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <div ref={root} className={styles.reactionControls}>
    <button ref={trigger} type="button" className={`signal-icon-button ${styles.reactButton}`} aria-label="React to message" aria-expanded={open} disabled={busy} onClick={() => setOpen((value) => !value)}><Icon name="smile" size={18} /></button>
    {open && <div className={styles.reactionPicker} data-action-menu role="group" aria-label="Choose emoji reaction">{emojis.map((emoji) => <button data-reaction-choice key={emoji} type="button" aria-label={`${mine(emoji) ? "Remove" : "Add"} ${emoji} reaction`} aria-pressed={mine(emoji)} disabled={busy} onClick={() => void toggle(emoji)}>{emoji}</button>)}</div>}
    {reactions.length > 0 && <div className={styles.reactions} aria-label="Message reactions">{emojis.filter((emoji) => reactions.some((r) => r.emoji === emoji)).map((emoji) => {
      const count = reactions.filter((r) => r.emoji === emoji).length;
      return <button key={emoji} type="button" aria-pressed={mine(emoji)} disabled={busy} aria-label={`${emoji}, ${count} reaction${count === 1 ? "" : "s"}${mine(emoji) ? ", including yours; remove yours" : "; add yours"}`} onClick={() => void toggle(emoji)}>{emoji} <span>{count}</span></button>;
    })}</div>}
    {error && <p className={styles.reactionError} role="alert">{error}</p>}
  </div>;
}
