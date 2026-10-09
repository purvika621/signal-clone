import type { ConversationPreview, PreviewMessage, Profile } from "./types";

// Isolated Phase 3A fixture: no API calls, database writes, or simulated sends.
export const previewUser: Profile = { id: "you", name: "You", avatar: "/avatars/alex.jpg" };
const maya: Profile = { id: "maya", name: "Maya Johnson", avatar: "/avatars/maya.jpg", color: "#7856c8" };
const paige: Profile = { id: "paige", name: "Paige Hall", avatar: "/avatars/paige.jpg", color: "#927243" };
const kai: Profile = { id: "kai", name: "Kai Guo", avatar: "/avatars/kai.jpg", color: "#7256cd" };
const mom: Profile = { id: "mom", name: "Mom", avatar: "/avatars/alex.jpg", color: "#38812c" };
const julian: Profile = { id: "julian", name: "Julian Rocha", avatar: "/avatars/kai.jpg", color: "#6852df" };
function message(id: string, sender: Profile, text: string, timestamp: string, dateLabel = "Today", receipt?: PreviewMessage["receipt"]): PreviewMessage {
  return { id, sender, text, timestamp, dateLabel, outgoing: sender.id === previewUser.id, receipt };
}
export const previewConversations: ConversationPreview[] = [
  {
    id: "maya", kind: "direct", profile: maya, activity: "8m", preview: "You: Got it. See you in a few!", unread: 0, receipt: "delivered", bubbleColor: "#2867f5",
    messages: [
      message("m1", maya, "Are you still coming over tomorrow?", "6:42 PM", "Yesterday"),
      message("m2", previewUser, "Of course! I wouldn’t miss it.", "6:43 PM", "Yesterday", "read"),
      message("m3", maya, "Perfect. See you then!", "6:44 PM", "Yesterday"),
      message("m4", previewUser, "I’m on my way! What’s the address?", "30m", "Today", "read"),
      message("m5", maya, "We’re at 118 68th Ave.", "25m"),
      message("m6", previewUser, "Is there a buzzer? Don’t want to ruin the surprise", "20m", "Today", "read"),
      message("m7", maya, "Buzz 2F if you get here before 7pm otherwise text me and I’ll come down to get you", "10m"),
      message("m8", previewUser, "Got it. See you in a few!", "8m", "Today", "delivered"),
    ],
  },
  {
    id: "family", kind: "group", profile: { id: "family", name: "Family", avatar: "/avatars/family.jpg" }, activity: "30m", preview: "Mom: I’ll bring the old photo albums.", unread: 3, bubbleColor: "#cf1242",
    messages: [
      message("f1", mom, "Does everyone have time to come over this weekend?", "5:10 PM", "Yesterday"),
      message("f2", previewUser, "Sunday works for me.", "5:12 PM", "Yesterday", "read"),
      message("f3", julian, "I found some photos from Dad’s trip to LA in 1972.", "1h"),
      message("f4", mom, "That was outside João’s house. They were such good friends.", "45m"),
      message("f5", previewUser, "Remind me, who was João?", "40m", "Today", "read"),
      message("f6", mom, "His friend from college! They stayed in touch for years.", "35m"),
      message("f7", julian, "There are so many stories I haven’t heard yet.", "32m"),
      message("f8", mom, "I’ll bring the old photo albums.", "30m"),
    ],
  },
  {
    id: "paige", kind: "direct", profile: paige, activity: "50m", preview: "Yeah, I just got the group link — thanks for adding me", unread: 0, bubbleColor: "#2867f5",
    messages: [message("p1", previewUser, "We’re planning a dinner for next Thursday.", "1h", "Today", "read"), message("p2", paige, "That sounds lovely!", "55m"), message("p3", paige, "Yeah, I just got the group link — thanks for adding me", "50m")],
  },
  {
    id: "climbers", kind: "group", profile: { id: "climbers", name: "Rock climbers", avatar: "/avatars/climbers.jpg" }, activity: "9:30 AM", preview: "Kai: OK, I’m picking everyone up at 8am tomorrow. Be ready to pile into the car.", unread: 0, bubbleColor: "#2867f5",
    messages: [message("c1", paige, "The forecast looks good for tomorrow.", "9:15 AM"), message("c2", previewUser, "I’ve packed everything. Can’t wait!", "9:18 AM", "Today", "read"), message("c3", kai, "OK, I’m picking everyone up at 8am tomorrow. Be ready to pile into the car.", "9:30 AM")],
  },
  {
    id: "notes", kind: "direct", profile: { id: "notes", name: "Note to Self", noteToSelf: true }, activity: "Tue", preview: "Groceries: Coffee, yogurt, grapefruit, biscuits", unread: 0, receipt: "read", bubbleColor: "#2867f5",
    messages: [message("n1", previewUser, "Groceries: Coffee, yogurt, grapefruit, biscuits", "10:15 AM", "Tuesday", "read")],
  },
  {
    id: "roommates", kind: "group", profile: { id: "roommates", name: "Roommates", avatar: "/avatars/roommates.jpg" }, activity: "Tue", preview: "Kai: Working late — can one of you please feed Spooky?", unread: 1, bubbleColor: "#2867f5",
    messages: [message("r1", previewUser, "Let’s grab dinner together this week. Does Thursday work for everyone?", "5:30 PM", "Tuesday", "read"), message("r2", kai, "Yes! We haven’t been out in forever", "5:32 PM", "Tuesday"), message("r3", previewUser, "What sounds good?", "5:33 PM", "Tuesday", "read"), message("r4", paige, "Italian?", "5:34 PM", "Tuesday"), message("r5", kai, "Working late — can one of you please feed Spooky?", "6:10 PM", "Tuesday")],
  },
  {
    id: "soup", kind: "group", profile: { id: "soup", name: "Winter Soup Club", avatar: "/avatars/soup.jpg" }, activity: "Tue", preview: "Perfect, see you all in a few days!", unread: 0, bubbleColor: "#2867f5",
    messages: [message("s1", paige, "I’m making tomato soup this time.", "4:10 PM", "Tuesday"), message("s2", previewUser, "I’ll bring the bread.", "4:12 PM", "Tuesday", "sent"), message("s3", maya, "Perfect, see you all in a few days!", "4:15 PM", "Tuesday")],
  },
];
