import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "PornScraper by Porn-Pros — Procesamiento de contenido público",
  description: "Descargá audio y video desde cualquier dispositivo.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/pornbros-mark.svg", apple: "/pornbros-mark.svg" },
};

export const viewport = {
  themeColor: "#09080b",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>{children}</body>
    </html>
  );
}
