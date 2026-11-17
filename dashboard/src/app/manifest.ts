import type { MetadataRoute } from "next";

// Convención de Next.js (app/manifest.ts): se sirve como /manifest.webmanifest y el <link
// rel="manifest"> se inyecta solo en el <head> -- no hace falta enlazarlo a mano en layout.tsx.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "MindOS",
    short_name: "MindOS",
    description: "Captura, busca y explora tu memoria de largo plazo.",
    start_url: "/capture",
    scope: "/",
    display: "standalone",
    background_color: "#0c141c",
    theme_color: "#0c141c",
    orientation: "portrait-primary",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    share_target: {
      action: "/api/share-target",
      method: "POST",
      enctype: "multipart/form-data",
      params: {
        title: "title",
        text: "text",
        url: "url",
        files: [{ name: "files", accept: ["image/*", "audio/*", "application/pdf"] }],
      },
    },
  };
}
