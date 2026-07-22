// Service worker de MindOS (F4-T3): app shell offline-first + intercepción del share_target.
// Deliberadamente sin Workbox/next-pwa: Turbopack (Next.js 16) no tiene un plugin PWA con
// compatibilidad confirmada, y la estrategia que hace falta aquí (cachear-mientras-navegas +
// interceptar una sola ruta de share-target) es simple de escribir a mano sin esa dependencia.
const RUNTIME_CACHE = "mindos-runtime-v1";
const SHARE_CACHE = "mindos-share-target-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (event.request.method === "POST" && url.pathname === "/api/share-target") {
    event.respondWith(handleShareTarget(event.request));
    return;
  }

  // Solo GET del mismo origen se cachea -- las llamadas al Gateway (otro origen) van siempre
  // a la red: cachearlas arriesgaría servir datos de conocimiento obsoletos como si fueran vivos.
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;

  event.respondWith(networkFirstWithCache(event.request));
});

async function networkFirstWithCache(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    // Sin nada cacheado para esta URL exacta: para una navegación, la Captura (start_url de la
    // PWA) es el shell más útil que sí podemos servir sin red.
    if (request.mode === "navigate") {
      const shell = await cache.match("/capture");
      if (shell) return shell;
    }
    throw new Error("Sin red y sin copia en cache para esta petición.");
  }
}

async function handleShareTarget(request) {
  const formData = await request.formData();
  const payload = {
    title: formData.get("title") || "",
    text: formData.get("text") || "",
    url: formData.get("url") || "",
  };
  const files = formData.getAll("files").filter((f) => f && f.size > 0);

  const cache = await caches.open(SHARE_CACHE);
  await cache.put("/__share-payload", new Response(JSON.stringify(payload)));
  if (files.length > 0) {
    await cache.put(
      "/__share-file",
      new Response(files[0], { headers: { "Content-Type": files[0].type || "application/octet-stream" } }),
    );
  } else {
    await cache.delete("/__share-file");
  }

  return Response.redirect("/capture?shared=1", 303);
}
