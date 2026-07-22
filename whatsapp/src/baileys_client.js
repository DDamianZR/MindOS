import makeWASocket, { DisconnectReason, useMultiFileAuthState } from "@whiskeysockets/baileys";
import pino from "pino";
import qrcode from "qrcode-terminal";

/**
 * Conecta con WhatsApp vía Baileys (F3-T4), persistiendo la sesión en `authDir` (debe ser un
 * volumen Docker persistente — nunca se sube al repo). Reconecta automáticamente salvo que la
 * sesión haya sido cerrada explícitamente desde el teléfono (logout real).
 *
 * `onMessage(waMessage, botJid, sock)` se invoca por cada mensaje entrante nuevo (no propio);
 * `sock` se pasa para que quien reciba pueda descargar medios adjuntos (`downloadMediaMessage`
 * necesita el socket activo para re-solicitar el medio a WhatsApp si el link inicial expiró).
 * `onSocketReady(sock)` se invoca con el socket activo cada vez que se (re)conecta — necesario
 * porque tras una reconexión Baileys entrega un socket NUEVO, no reutiliza el anterior.
 *
 * Sin conexión real a WhatsApp no se puede verificar en este entorno de desarrollo (requiere
 * escanear un QR con un teléfono real) — ver plan/NOTAS.md.
 */
export async function connectToWhatsApp(authDir, onMessage, onSocketReady) {
  const { state, saveCreds } = await useMultiFileAuthState(authDir);
  const sock = makeWASocket({
    auth: state,
    logger: pino({ level: "silent" }),
  });

  sock.ev.on("creds.update", saveCreds);

  sock.ev.on("connection.update", (update) => {
    const { connection, lastDisconnect, qr } = update;
    if (qr) {
      console.log("Escanea este QR desde WhatsApp > Dispositivos vinculados:");
      qrcode.generate(qr, { small: true });
    }
    if (connection === "open") {
      console.log("WhatsApp conectado.");
    }
    if (connection === "close") {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = statusCode === DisconnectReason.loggedOut;
      console.warn(`Conexión de WhatsApp cerrada (código ${statusCode}).`, loggedOut ? "Sesión cerrada desde el teléfono, no se reintenta." : "Reintentando...");
      if (!loggedOut) {
        connectToWhatsApp(authDir, onMessage, onSocketReady);
      }
    }
  });

  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;
    for (const msg of messages) {
      if (msg.key.fromMe || !msg.message) continue;
      await onMessage(msg, sock.user?.id, sock);
    }
  });

  onSocketReady(sock);
  return sock;
}
