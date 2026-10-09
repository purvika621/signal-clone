import type { ReceiptStatus } from "@/features/messaging/types";
import styles from "./workspace.module.css";

export function Receipt({ status }: { status: ReceiptStatus }) {
  const double = status !== "sent";
  const filled = status === "read";
  return <span className={`${styles.receipt} ${filled ? styles.receiptRead : ""}`} role="img" aria-label={status} title={status}>
    <svg width={double ? 21 : 15} height="16" viewBox={double ? "0 0 25 18" : "0 0 18 18"} aria-hidden="true">
      <circle cx="9" cy="9" r="7" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.2" />
      {!double && <path d="m5.5 9 2.3 2.3 4.6-5" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />}
      {double && <><circle cx="16" cy="9" r="7" fill={filled ? "currentColor" : "var(--receipt-background, var(--signal-bubble-incoming))"} stroke="currentColor" strokeWidth="1.2" /><path d="m12.5 9 2.3 2.3 4.6-5" fill="none" stroke={filled ? "var(--receipt-background, #fff)" : "currentColor"} strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" /></>}
    </svg>
  </span>;
}
