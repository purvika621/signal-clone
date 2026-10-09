"use client";
import { useEffect, useRef, useState } from "react";
import { IconButton } from "@/components/ui/icon-button";
import styles from "@/components/ui/overlays.module.css";
import { Avatar } from "@/components/ui/avatar";
import { presence, profile, type User } from "@/features/messaging/api";

export type Destination = "Settings" | "Calls" | "Stories" | "Linked devices";
const categories = ["Privacy", "Notifications", "Appearance", "Linked devices"] as const;
const descriptions = {
  Privacy: "Privacy controls are Coming Soon. This demo stores plaintext messages and does not implement Signal encryption or real phone verification.",
  Notifications: "Notification preferences are Coming Soon. In-app message toasts are available; operating-system notifications are not enabled and no browser permission is requested.",
  Appearance: "Appearance controls are Coming Soon. This checkpoint uses the reviewed light desktop theme; dark mode is deferred.",
  "Linked devices": "Device linking is Coming Soon. Sign in with a demo identifier in separate browser sessions instead of pairing a Signal device.",
};
export function SettingsDialog({ destination, onClose }: { destination: Destination; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [category, setCategory] = useState<(typeof categories)[number]>(destination === "Linked devices" ? "Linked devices" : "Privacy");
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  const settings = destination === "Settings" || destination === "Linked devices";
  return <dialog ref={dialog} className={styles.dialog} aria-labelledby="destination-title" onCancel={onClose}><header className={styles.dialogHeader}><h2 id="destination-title">{settings ? "Settings" : destination}</h2><IconButton icon="close" label="Close" onClick={onClose} /></header>{settings ? <div className={styles.settings}><nav className={styles.categories} aria-label="Settings categories">{categories.map((name) => <button type="button" key={name} aria-current={category === name ? "true" : undefined} onClick={() => setCategory(name)}>{name}</button>)}</nav><section className={styles.placeholder} aria-label={`${category} settings`}><h3>{category}</h3><span className={styles.comingSoon}>Coming Soon</span><p>{descriptions[category]}</p></section></div> : <section className={styles.placeholder}><h3>{destination}</h3><span className={styles.comingSoon}>Coming Soon</span><p>{destination === "Calls" ? "Voice and video calls are placeholders in this assignment. Text messaging remains available in Chats." : "Stories are a placeholder in this assignment. Return to Chats to continue messaging."}</p></section>}</dialog>;
}

export function ContactDetailsDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current!; element.showModal(); return () => element.close(); }, []);
  return <dialog ref={dialog} className={styles.dialog} aria-label="Contact details" onCancel={onClose}><header className={styles.dialogHeader}><h2>Contact details</h2><IconButton icon="close" label="Close" onClick={onClose} /></header><section className={styles.placeholder}><Avatar profile={profile(user)} size={64} /><h3>{user.display_name}</h3><p>{user.username ? `@${user.username}` : user.phone_e164}</p><p>{presence(user)}</p></section></dialog>;
}
