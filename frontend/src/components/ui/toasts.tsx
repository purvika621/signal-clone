"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Icon } from "./icon";
import styles from "./overlays.module.css";

type ToastInput = { title: string; body?: string; action?: () => void; conversationId?: string };
type Toast = ToastInput & { id: number; expires: number };
const Context = createContext<{ notify: (input: ToastInput) => void; clear: () => void; dismissConversation: (id: string) => void } | null>(null);
export function useToasts() { const context = useContext(Context); if (!context) throw new Error("ToastProvider is required"); return context; }
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const next = useRef(0);
  const notify = useCallback((input: ToastInput) => { const item = { ...input, id: ++next.current, expires: Date.now() + 6500 }; setItems((previous) => [...previous.slice(-3), item]); }, []);
  const clear = useCallback(() => setItems([]), []);
  const dismissConversation = useCallback((id: string) => setItems((previous) => previous.filter((item) => item.conversationId !== id)), []);
  useEffect(() => { if (!items.length) return; const timer = setTimeout(() => setItems((previous) => previous.filter((item) => item.expires > Date.now())), Math.max(0, Math.min(...items.map((item) => item.expires)) - Date.now())); return () => clearTimeout(timer); }, [items]);
  const value = useMemo(() => ({ notify, clear, dismissConversation }), [notify, clear, dismissConversation]);
  return <Context.Provider value={value}>{children}<div className={styles.toasts} aria-live="polite" aria-relevant="additions" aria-label="Notifications">{items.map((item) => <div key={item.id} className={styles.toast}><button type="button" className={styles.toastContent} disabled={!item.action} onClick={() => { item.action?.(); setItems((previous) => previous.filter((t) => t.id !== item.id)); }}><strong>{item.title}</strong>{item.body && <span>{item.body}</span>}</button><button className="signal-icon-button" type="button" aria-label="Dismiss notification" onClick={() => setItems((previous) => previous.filter((t) => t.id !== item.id))}><Icon name="close" size={16} /></button></div>)}</div></Context.Provider>;
}
