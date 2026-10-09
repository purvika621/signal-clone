import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signal Desktop Clone",
  description: "Signal Desktop messaging workspace visual checkpoint",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
