import type { ReactNode } from "react";
export type IconName = "menu" | "chat" | "phone" | "stories" | "settings" | "compose" | "more" | "search" | "video" | "smile" | "sticker" | "microphone" | "plus" | "note" | "close" | "back" | "send" | "clock";
const paths: Record<IconName, ReactNode> = {
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 6v6l4 2" /></>,
  send: <><path d="m3 3 19 9-19 9 4-9-4-9ZM7 12h15" /></>,
  back: <path d="m12 4-8 8 8 8M4 12h17" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  chat: <path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5H5l-3 2 1.6-5.2A8.5 8.5 0 1 1 21 11.5Z" />,
  phone: <path d="m7.2 3.5 2.5 4.1c.4.7.2 1.3-.3 1.8l-1.5 1.5c1.1 2.1 2.8 3.8 4.9 4.9l1.5-1.5c.5-.5 1.1-.7 1.8-.3l4.1 2.5c.7.4.9 1.2.5 1.9l-1 1.5c-.8 1.1-2.2 1.5-3.5 1-6.7-2.1-11.9-7.3-14-14-.4-1.3 0-2.7 1.1-3.5l1.5-1c.8-.4 1.6-.2 1.9.5Z" />,
  stories: <><rect x="7" y="3" width="14" height="18" rx="3" /><path d="m4 5-1 .3a2 2 0 0 0-1.3 2.5l3.3 11" /></>,
  settings: <><path d="m9.3 3-.5 2.1-2 .9L4.9 5l-2 3.5 1.5 1.5-.2 2 .2 2-1.5 1.5 2 3.5 1.9-1 2 .9.5 2.1h4.2l.5-2.1 2-.9 1.9 1 2-3.5-1.5-1.5.2-2-.2-2L21 8.5 19 5l-1.9 1-2-.9-.5-2.1Z" /><circle cx="11.4" cy="12" r="3.6" /></>,
  compose: <><path d="M13 4H6a3 3 0 0 0-3 3v11a3 3 0 0 0 3 3h11a3 3 0 0 0 3-3v-7" /><path d="m19.1 2.9 2 2a1.3 1.3 0 0 1 0 1.8L11 16.8l-4 1 1-4L18.1 2.9a.7.7 0 0 1 1 0Z" /></>,
  more: <>{[4, 12, 20].map((x) => <circle key={x} cx={x} cy="12" r="1.6" fill="currentColor" stroke="none" />)}</>,
  search: <><circle cx="10.5" cy="10.5" r="7.5" /><path d="m16 16 6 6" /></>,
  video: <><rect x="2" y="5" width="13" height="14" rx="3" /><path d="m15 9 6-4v14l-6-4" /></>,
  smile: <><circle cx="12" cy="12" r="10" /><circle cx="8.4" cy="9" r="1.1" fill="currentColor" stroke="none" /><circle cx="15.6" cy="9" r="1.1" fill="currentColor" stroke="none" /><path d="M7 14a5.5 5.5 0 0 0 10 0" /></>,
  sticker: <><path d="M21 12V6a3 3 0 0 0-3-3H6a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3h6Z" /><path d="M12 21v-6a3 3 0 0 1 3-3h6" /></>,
  microphone: <><rect x="8" y="2" width="8" height="14" rx="4" /><path d="M4 10v2a8 8 0 0 0 16 0v-2M12 20v3M8 23h8" /></>,
  plus: <path d="M12 3v18M3 12h18" />,
  note: <><rect x="4" y="2" width="16" height="20" rx="3" /><path d="M4 7h16M8 12h8M8 16h8M8 19h4" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
};
export function Icon({ name, size = 24, filled = false }: { name: IconName; size?: number; filled?: boolean }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
