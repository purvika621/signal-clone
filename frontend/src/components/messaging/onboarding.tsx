"use client";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "@/lib/api";
import { challenge, errorMessage, restoreSession, saveProfile, signIn, signOut, type Session, type User } from "@/features/messaging/api";
import { Avatar } from "@/components/ui/avatar";
import { SignalWorkspace } from "./signal-workspace";
import styles from "./onboarding.module.css";
import { ToastProvider, useToasts } from "@/components/ui/toasts";

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className={styles.error}>{message}{onRetry && <button type="button" onClick={onRetry}>Retry</button>}</div>;
}

function Login({ onSession }: { onSession: (session: Session) => void }) {
  const [identifier, setIdentifier] = useState("alex");
  const [verification, setVerification] = useState<{ identifier: string; mock_code: string; message: string } | null>(null);
  const [otp, setOtp] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (verification) onSession(await signIn(verification.identifier, otp));
      else setVerification(await challenge(identifier));
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <section className={styles.card} aria-label="Demo sign in"><span className={styles.brand}>Signal</span><h1>{verification ? "Verify your demo account" : "Welcome to Signal"}</h1>
    <p>This assignment uses mocked registration and login, without SMS, device pairing or Signal encryption.</p>
    <form onSubmit={submit}>
      {verification ? <><p>{verification.message}</p><p>Signing in as <strong>{verification.identifier}</strong>. Demo code: <strong>{verification.mock_code}</strong></p><label>Verification code<input autoFocus inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={otp} onChange={(e) => setOtp(e.target.value)} /></label></> : <><label>Username or international phone number<input autoFocus required minLength={3} maxLength={100} autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} /></label><p>Demo users: <button type="button" className={styles.link} onClick={() => setIdentifier("alex")}>alex</button> or <button type="button" className={styles.link} onClick={() => setIdentifier("maya")}>maya</button>. A new identifier registers a new user.</p></>}
      {error && <ErrorNotice message={error} />}
      <button className={styles.primary} disabled={busy} type="submit">{busy ? "Please wait…" : verification ? "Sign in" : "Continue"}</button>
      {verification && <button type="button" disabled={busy} onClick={() => { setVerification(null); setOtp(""); setError(""); }}>Use another account</button>}
    </form></section>;
}

export function ProfileForm({ user, onSave, onLogout, onCancel }: { user: User; onSave: (session: Session) => void; onLogout: () => Promise<void>; onCancel?: () => void }) {
  const { notify } = useToasts();
  const [name, setName] = useState(user.display_name);
  const [avatar, setAvatar] = useState(user.avatar_url ?? `/avatars/${["alex", "maya", "kai", "paige"].includes(user.username ?? "") ? user.username : "alex"}.jpg`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { onSave(await saveProfile(name, avatar)); notify({ title: "Profile saved" }); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  }
  return <section className={styles.card} aria-label="Your profile"><h1>Your profile</h1><p>Choose the name and avatar other demo users will see.</p><form onSubmit={save}>
    <label>Display name<input autoFocus required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} /></label>
    <fieldset disabled={busy}><legend>Profile avatar</legend><div className={styles.avatars}>{["alex", "maya", "kai", "paige", "family", "climbers"].map((key) => {
      const value = `/avatars/${key}.jpg`;
      return <label key={key}><input type="radio" name="avatar" aria-label={`${key} avatar`} checked={avatar === value} onChange={() => setAvatar(value)} /><Avatar profile={{ id: key, name: key, avatar: value }} size={48} /></label>;
    })}</div></fieldset>
    {error && <ErrorNotice message={error} />}
    <button className={styles.primary} disabled={busy} type="submit">{busy ? "Saving…" : "Save profile"}</button>
    {onCancel && <button type="button" disabled={busy} onClick={onCancel}>Cancel</button>}
    <button type="button" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { await onLogout(); } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); } }}>Log out</button>
  </form></section>;
}

export function MessagingApplication() {
  return <ToastProvider><Application /></ToastProvider>;
}

function Application() {
  const { clear, notify } = useToasts();
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<"loading" | "login" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    restoreSession(controller.signal).then((result) => { if (active) { setSession(result); setState("ready"); } }).catch((e) => {
      if (!active) return;
      if (e instanceof ApiError && e.status === 401) setState("login");
      else { setError(errorMessage(e)); setState("error"); }
    });
    return () => { active = false; controller.abort(); };
  }, [attempt]);
  function accept(result: Session) { setSession(result); setState("ready"); setEditing(false); }
  async function logout() {
    try { await signOut(); } catch (e) { if (!(e instanceof ApiError && e.status === 401)) throw e; }
    setSession(null); setEditing(false); setState("login"); window.history.replaceState(null, "", "/");
    clear(); notify({ title: "Logged out" });
  }
  return <div data-signal-application="true">
    {state === "ready" && session && !session.needs_profile ? <><SignalWorkspace key={session.user.id} user={session.user} readingPaused={editing} onProfile={() => setEditing(true)} />{editing && <ProfileDialog user={session.user} onSave={accept} onLogout={logout} onCancel={() => setEditing(false)} />}</> : <main className={styles.onboarding}><div className={styles.onboardingContent}>
      <aside className={styles.demoNotice} aria-label="Unofficial assignment demo notice">Unofficial Signal UI assignment demo. Not affiliated with Signal. Use fictional details and demo OTP 123456. Never enter real passwords or real verification codes.</aside>
      {state === "loading" && <p role="status">Restoring your session…</p>}
      {state === "error" && <section className={styles.card}><h1>Unable to connect</h1><ErrorNotice message={error} onRetry={() => { setState("loading"); setAttempt((a) => a + 1); }} /></section>}
      {state === "login" && <Login onSession={accept} />}
      {state === "ready" && session?.needs_profile && <ProfileForm user={session.user} onSave={accept} onLogout={logout} />}
    </div></main>}
  </div>;
}

function ProfileDialog(props: Parameters<typeof ProfileForm>[0]) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  return <dialog ref={ref} className={styles.dialog} aria-label="Edit profile" onCancel={props.onCancel}><ProfileForm {...props} /></dialog>;
}
