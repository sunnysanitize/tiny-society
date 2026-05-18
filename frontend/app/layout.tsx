import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tiny Society AI",
  description: "Multi-agent social simulation with AI agent reasoning.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
