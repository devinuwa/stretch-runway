import type { Metadata } from "next";
import "./globals.css";

/**
 * Privacy rules (AGENTS.md §4): no CDN assets, no remote/Google fonts, no
 * analytics. Fonts are the local system stack declared in globals.css.
 */
export const metadata: Metadata = {
  title: "Stretch — runway, not advice",
  description:
    "Local-first, privacy-first runway scenarios for money that arrives in unpredictable bits. No bank connection, no cloud.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full bg-zinc-50 text-zinc-900 antialiased dark:bg-zinc-950 dark:text-zinc-100">
        {children}
      </body>
    </html>
  );
}
