import { Icon, type IconName } from "./icon";
type IconButtonProps = { icon: IconName; label: string; onClick?: () => void; unavailable?: boolean; selected?: boolean; className?: string; size?: number };
export function IconButton({ icon, label, onClick, unavailable, selected, className = "", size = 24 }: IconButtonProps) {
  return <button type="button" className={`signal-icon-button ${className}`} aria-label={label} title={unavailable ? `${label} — unavailable in this visual checkpoint` : label} aria-pressed={selected} disabled={unavailable} onClick={onClick}><Icon name={icon} size={size} filled={icon === "chat" && selected} /></button>;
}
