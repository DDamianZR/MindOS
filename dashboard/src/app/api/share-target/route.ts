import { NextResponse } from "next/server";

// Red de seguridad, no el camino normal: el service worker (public/sw.js) intercepta el POST
// del share_target ANTES de que llegue aquí, guarda lo compartido y redirige a /capture?shared=1
// -- eso mantiene la carga real autenticada con el JWT del cliente, en vez de intentar
// reenviarla desde este handler de servidor (que no tiene acceso al localStorage del usuario).
// Si el SW aún no está activo (primer share antes de que termine de registrarse), esta ruta
// evita al menos un 404 crudo, aunque el contenido compartido se pierda en ese caso puntual.
export async function POST(request: Request) {
  return NextResponse.redirect(new URL("/capture", request.url), { status: 303 });
}
