import Image from "next/image";
import type { Profile } from "@/features/messaging/types";
import { Icon } from "./icon";
export function Avatar({ profile, size = 46 }: { profile: Profile; size?: number }) {
  return <span className={`signal-avatar${profile.noteToSelf ? " signal-avatar-note" : ""}`} style={{ width: size, height: size }} aria-hidden="true">
    {profile.noteToSelf ? <Icon name="note" size={size * 0.52} /> : profile.avatar ? <Image src={profile.avatar} alt="" width={size} height={size} unoptimized /> : <span>{profile.name.split(" ").map((word) => word[0]).slice(0, 2).join("")}</span>}
  </span>;
}
