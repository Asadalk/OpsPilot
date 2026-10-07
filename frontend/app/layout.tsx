import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ops Pilot",
  description: "AI Internal Ops Pilot",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-800 bg-slatebrand-950 text-white">
          <div className="mx-auto max-w-7xl px-6 py-4 text-lg font-semibold tracking-wide">
            Ops Pilot
          </div>
        </header>
        <main className="mx-auto min-h-[calc(100vh-65px)] max-w-7xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
