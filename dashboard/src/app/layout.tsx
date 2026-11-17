import type { Metadata, Viewport } from "next";
import { Archivo, Geist_Mono, Piazzolla } from "next/font/google";
import "./globals.css";

import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { AuthProvider } from "@/lib/auth";

// Archivo (interfaz) y Piazzolla (lectura larga) vienen de la misma fundición, Omnibus-Type, y
// Piazzolla se diseñó para texto denso en español: acentos, ñ y signos de apertura bien resueltos.
const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
});

const piazzolla = Piazzolla({
  variable: "--font-piazzolla",
  subsets: ["latin"],
  style: ["normal", "italic"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MindOS",
  description: "Tu memoria de largo plazo: conversa con ella, explora cómo se conecta y guarda lo que no quieres perder.",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "MindOS" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f3f5f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0c141c" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="es"
      className={`${archivo.variable} ${piazzolla.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex h-full min-h-full flex-col">
        <ServiceWorkerRegistration />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
