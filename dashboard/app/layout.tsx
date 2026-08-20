import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PeoplePulse AI Dashboard",
  description: "Privacy-aware workforce intelligence portfolio dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
