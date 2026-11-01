import type { Metadata, Viewport } from "next";
import {
  Anek_Bangla,
  Anek_Devanagari,
  Anek_Gujarati,
  Anek_Gurmukhi,
  Anek_Kannada,
  Anek_Latin,
  Anek_Malayalam,
  Anek_Tamil,
  Anek_Telugu,
  Fraunces,
} from "next/font/google";
import "./globals.css";

// One type family across every script Kettu shows, so Malayalam, Bengali and Hindi sit together evenly.
const latin = Anek_Latin({ subsets: ["latin"], variable: "--f-latin", display: "swap" });
const ml = Anek_Malayalam({ subsets: ["malayalam"], variable: "--f-ml", display: "swap", preload: false });
const bn = Anek_Bangla({ subsets: ["bengali"], variable: "--f-bn", display: "swap", preload: false });
const dev = Anek_Devanagari({ subsets: ["devanagari"], variable: "--f-dev", display: "swap", preload: false });
const ta = Anek_Tamil({ subsets: ["tamil"], variable: "--f-ta", display: "swap", preload: false });
const te = Anek_Telugu({ subsets: ["telugu"], variable: "--f-te", display: "swap", preload: false });
const kn = Anek_Kannada({ subsets: ["kannada"], variable: "--f-kn", display: "swap", preload: false });
const gu = Anek_Gujarati({ subsets: ["gujarati"], variable: "--f-gu", display: "swap", preload: false });
const pa = Anek_Gurmukhi({ subsets: ["gurmukhi"], variable: "--f-pa", display: "swap", preload: false });
const display = Fraunces({ subsets: ["latin"], variable: "--f-display", display: "swap", axes: ["SOFT", "opsz"] });

const fontVars = [latin, ml, bn, dev, ta, te, kn, gu, pa, display].map((f) => f.variable).join(" ");

export const metadata: Metadata = {
  title: "Kettu · voice notes, understood",
  description:
    "Share any WhatsApp voice note to Kettu. Read it in your language and reply with a voice note in theirs. Built on Gnani Prisma and Timbre.",
  applicationName: "Kettu",
  appleWebApp: { capable: true, title: "Kettu", statusBarStyle: "default" },
  icons: {
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
    apple: [{ url: "/icons/apple-touch-icon.png", sizes: "180x180" }],
  },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f6efe4" },
    { media: "(prefers-color-scheme: dark)", color: "#1c1714" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVars}>
      <body>{children}</body>
    </html>
  );
}
