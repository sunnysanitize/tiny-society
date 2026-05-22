import "./globals.css";
import type { Metadata } from "next";
import { Press_Start_2P } from "next/font/google";

const pixelFont = Press_Start_2P({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-pixel",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Tiny Society AI",
  description: "Multi-agent social simulation with AI agent reasoning.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={pixelFont.variable}>
      <body>{children}</body>
    </html>
  );
}
