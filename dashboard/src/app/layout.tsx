import type { Metadata, Viewport } from "next";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";
import "./globals.css";

import { ServiceWorkerRegistration } from "@/components/ServiceWorkerRegistration";
import { AuthProvider } from "@/lib/auth";

// Inter Tight: la sans de todo el sistema (texto, títulos, navegación), con tracking negativo
// en tamaños grandes. JetBrains Mono: la voz mono de etiquetas, insignias y botones.
const interTight = Inter_Tight({
  variable: "--font-inter-tight",
  subsets: ["latin"],
});

const jetBrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MindOS",
  description: "Tu memoria de largo plazo, con un agente que la consulta, la conecta y actúa por ti.",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "MindOS" },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${interTight.variable} ${jetBrainsMono.variable} h-full antialiased`}>
      <body className="flex h-full min-h-full flex-col">
        <ServiceWorkerRegistration />
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
