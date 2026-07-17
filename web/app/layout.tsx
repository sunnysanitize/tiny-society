import "./globals.css";
import type { Metadata } from "next";
import { Fredoka } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";

// Friendly, rounded, highly-legible display font used for buttons, tags and
// labels (exposed via the --font-pixel CSS variable, kept for compatibility).
const pixelFont = Fredoka({
  weight: ["400", "500", "600", "700"],
  subsets: ["latin"],
  variable: "--font-pixel",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Tiny Society AI",
  description: "AI character reasoning.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={pixelFont.variable}>
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
