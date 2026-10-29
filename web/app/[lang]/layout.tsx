import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import { getDictionary, localeOf } from "@/lib/i18n";
import "../globals.css";

const instrument = Instrument_Sans({ subsets: ["latin"], variable: "--font-instrument" });

export async function generateMetadata({ params }: LayoutProps<"/[lang]">): Promise<Metadata> {
  const d = getDictionary((await params).lang);
  return { title: d.meta.title, description: d.meta.description, robots: { index: false, follow: false } };
}

export default async function RootLayout({ children, params }: LayoutProps<"/[lang]">) {
  const lang = localeOf((await params).lang);
  return (
    <html lang={lang} className={instrument.variable}>
      <body className="min-h-screen font-sans antialiased">{children}</body>
    </html>
  );
}
