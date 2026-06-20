import "./globals.css";
import type { Metadata } from "next";
import { Press_Start_2P } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { SplashScreen } from "@/components/SplashScreen";

const pixelFont = Press_Start_2P({
  weight: "400",
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
        <SplashScreen />
        {children}
        <Analytics />
      </body>
    </html>
  );
}
