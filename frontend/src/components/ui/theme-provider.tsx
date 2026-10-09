"use client";
import { createContext, useContext, useEffect, useSyncExternalStore, type ReactNode } from "react";

export type ThemePreference = "light" | "dark" | "system";
const key = "signal-theme";
const eventName = "signal-theme-changed";
let memoryPreference: ThemePreference = "system";
const ThemeContext = createContext<{ theme: ThemePreference; setTheme: (theme: ThemePreference) => void }>({ theme: "system", setTheme: () => {} });
function snapshot(): ThemePreference {
  try { const value = localStorage.getItem(key); return value === "light" || value === "dark" || value === "system" ? value : memoryPreference; }
  catch { return memoryPreference; }
}
function subscribe(callback: () => void) {
  const storage = (event: StorageEvent) => { if (event.key === key || event.key === null) { memoryPreference = "system"; callback(); } };
  window.addEventListener("storage", storage); window.addEventListener(eventName, callback);
  return () => { window.removeEventListener("storage", storage); window.removeEventListener(eventName, callback); };
}
function setTheme(theme: ThemePreference) {
  // Apply immediately even when browser storage is unavailable.
  memoryPreference = theme;
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(key, theme); } catch { /* Restricted browser storage. */ }
  window.dispatchEvent(new Event(eventName));
}
export function ThemeProvider({ children }: { children: ReactNode }) {
  const theme = useSyncExternalStore(subscribe, snapshot, () => "system" as const);
  useEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}
export function useTheme() { return useContext(ThemeContext); }
