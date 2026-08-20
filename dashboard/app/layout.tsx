import type { Metadata } from "next";
import "./globals.css";
import "./production.css";

export const metadata: Metadata = {
  title: "PeoplePulse HR Dashboard",
  description: "Production workforce support dashboard for HR operations",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
