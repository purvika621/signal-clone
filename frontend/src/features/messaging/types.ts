// Presentation view models shared by the API adapter and isolated visual fixture.
export type ReceiptStatus = "sent" | "delivered" | "read";
export type Profile = { id: string; name: string; avatar?: string; color?: string; noteToSelf?: boolean };
export type PreviewMessage = {
  id: string; kind?: "text" | "system"; sender: Profile; outgoing: boolean; text: string;
  timestamp: string; dateLabel: string; receipt?: ReceiptStatus;
  sequence?: number; clientId?: string; createdAt?: string;
  state?: "sending" | "failed"; failure?: string;
};
export type ConversationPreview = {
  id: string; kind: "direct" | "group"; profile: Profile; preview: string;
  activity: string; unread: number; receipt?: ReceiptStatus; bubbleColor: string;
  messages: PreviewMessage[];
  presence?: string;
};
