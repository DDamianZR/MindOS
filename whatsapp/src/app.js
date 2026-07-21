import express from "express";

/** JID de WhatsApp para un sender_id simple (F3-T4: contraparte de jidToSenderId). */
function senderIdToJid(recipientId) {
  return recipientId.includes("@") ? recipientId : `${recipientId}@s.whatsapp.net`;
}

/**
 * Fábrica del servidor Express (F3-T4), separada del arranque real de Baileys para poder
 * probar el contrato HTTP (`/health`, `/send`) con un `waClient` de prueba, sin conexión real.
 *
 * `waClient`: { getSock(): objeto Baileys o null si no conectado, isConnected(): bool }
 */
export function createApp(waClient, commsClient) {
  const app = express();
  app.use(express.json());

  app.get("/health", (_req, res) => {
    const connected = waClient.isConnected();
    res.status(200).json({ status: connected ? "ok" : "degraded", service: "whatsapp", connected });
  });

  app.post("/send", async (req, res) => {
    const { recipient_id: recipientId, text } = req.body || {};
    if (!recipientId || !text) {
      res.status(422).json({ detail: "recipient_id y text son obligatorios." });
      return;
    }

    const sock = waClient.getSock();
    if (!sock) {
      res.status(503).json({ detail: "WhatsApp no está conectado todavía." });
      return;
    }

    try {
      await sock.sendMessage(senderIdToJid(recipientId), { text });
      res.status(200).json({ status: "sent", recipient_id: recipientId });
    } catch (err) {
      res.status(502).json({ detail: `No se pudo enviar el mensaje: ${err.message}` });
    }
  });

  return app;
}

export { senderIdToJid };
