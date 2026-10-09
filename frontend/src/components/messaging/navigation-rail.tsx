import { Avatar } from "@/components/ui/avatar";
import { IconButton } from "@/components/ui/icon-button";
import type { Profile } from "@/features/messaging/types";
import styles from "./workspace.module.css";
import { ActionMenu } from "@/components/ui/action-menu";
import type { Destination } from "./settings-dialog";

export function NavigationRail({ user, onClearSelection, unread, onProfile, onDestination, onNewChat, onNewGroup }: { user: Profile; onClearSelection: () => void; unread: number; onProfile: () => void; onDestination: (destination: Destination) => void; onNewChat: () => void; onNewGroup: () => void }) {
  return <nav className={styles.rail} aria-label="Main navigation">
    <ActionMenu icon="menu" label="Main menu" left className={styles.railButton} items={[{ label: "Chats", action: onClearSelection }, { label: "New chat", action: onNewChat }, { label: "New group", action: onNewGroup }, { label: "Settings", action: () => onDestination("Settings") }, { label: "Linked devices", action: () => onDestination("Linked devices") }, { label: "Profile and logout", action: onProfile }]} />
    <div className={styles.railPrimary}>
      <div className={styles.railChat}>
        <IconButton icon="chat" label="Chats — clear conversation selection" selected onClick={onClearSelection} className={`${styles.railButton} ${styles.railSelected}`} />
        {unread > 0 && <span className={styles.railBadge} aria-label={`${unread} unread conversations`}>{unread}</span>}
      </div>
      <IconButton icon="phone" label="Calls" onClick={() => onDestination("Calls")} className={styles.railButton} />
      <IconButton icon="stories" label="Stories" onClick={() => onDestination("Stories")} className={styles.railButton} />
    </div>
    <div className={styles.railBottom}>
      <IconButton icon="settings" label="Settings" onClick={() => onDestination("Settings")} className={styles.railButton} />
      <button type="button" className={styles.profileButton} onClick={onProfile} title="Profile and logout" aria-label="Your profile and logout"><Avatar profile={user} size={32} /></button>
    </div>
  </nav>;
}
