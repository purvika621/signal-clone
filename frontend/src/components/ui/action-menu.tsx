"use client";
import { useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "./icon";
import styles from "./overlays.module.css";

export function ActionMenu({ label, icon = "more", items, left = false, className = "" }: { label: string; icon?: IconName; items: { label: string; action: () => void }[]; left?: boolean; className?: string }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    ref.current?.querySelector<HTMLButtonElement>("[data-menu-item]")?.focus();
    const dismiss = (event: PointerEvent) => { if (!ref.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    document.addEventListener("pointerdown", dismiss); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", dismiss); document.removeEventListener("keydown", escape); };
  }, [open]);
  return <div ref={ref} className={styles.menuAnchor}><button ref={trigger} type="button" className={`signal-icon-button ${className}`} aria-label={label} title={label} aria-expanded={open} onClick={() => setOpen((value) => !value)}><Icon name={icon} /></button>{open && <div className={`${styles.menu} ${left ? styles.menuLeft : ""}`} aria-label={label} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setOpen(false); }}>{items.map((item) => <button data-menu-item type="button" key={item.label} onClick={() => { setOpen(false); trigger.current?.focus(); item.action(); }}>{item.label}</button>)}</div>}</div>;
}
