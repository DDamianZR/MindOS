import { downloadMediaMessage } from "@whiskeysockets/baileys";
import pino from "pino";

import { createApp } from "./app.js";
import { connectToWhatsApp } from "./baileys_client.js";
import { createCommsClient } from "./comms_client.js";
import { toInboundPayload } from "./message_utils.js";

const silentLogger = pino({ level: "silent" });

const PORT = process.env.PORT || 8004;
const COMMS_URL = process.env.COMMS_URL || "http://localhost:8003";
const AUTH_DIR = process.env.WHATSAPP_AUTH_DIR || "/app/auth_state";

const commsClient = createCommsClient(COMMS_URL);

let currentSock = null;
const waClient = {
  getSock: () => currentSock,
  isConnected: () => currentSock !== null,
};

async function handleIncomingMessage(waMessage, botJid, sock) {
  const payload = toInboundPayload(waMessage, botJid || "");
  if (!payload.text && !payload.metadata.media_kind) return; // nada capturable (reacciones, recibos, etc.)

  if (payload.metadata.media_kind) {
    try {
      // F3-T5: el pipeline necesita los bytes reales, no solo el aviso de que hay un medio.
      // Van en base64 dentro de metadata (JSON) — MessageReceivedEventData.metadata ya es un
      // dict libre, no hace falta tocar el schema compartido.
      const buffer = await downloadMediaMessage(
        waMessage, "buffer", {}, { logger: silentLogger, reuploadRequest: sock.updateMediaMessage },
      );
      payload.metadata.media_base64 = buffer.toString("base64");
    } catch (err) {
      // Best-effort: si el medio ya no se puede descargar (link expirado, etc.), se captura
      // igual el texto/caption que haya en el mensaje en vez de perder el mensaje completo.
      console.error("No se pudo descargar el medio adjunto:", err.message);
    }
  }

  try {
    await commsClient.sendInbound(payload);
  } catch (err) {
    // Best-effort deliberado: un fallo de comms no debe tumbar el proceso del adaptador ni
    // perder la conexión de WhatsApp por un mensaje puntual — se registra para diagnóstico.
    console.error("No se pudo reenviar el mensaje entrante a comms:", err.message);
  }
}

async function main() {
  await connectToWhatsApp(AUTH_DIR, handleIncomingMessage, (sock) => {
    currentSock = sock;
  });

  const app = createApp(waClient, commsClient);
  app.listen(PORT, () => {
    console.log(`Adaptador de WhatsApp escuchando en el puerto ${PORT}.`);
  });
}

main().catch((err) => {
  console.error("Fallo crítico iniciando el adaptador de WhatsApp:", err);
  process.exit(1);
});
