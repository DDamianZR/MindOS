/**
 * Traducción de un mensaje Baileys a la forma canónica que espera POST /api/v1/comms/inbound
 * (F3-T4). Puro y sin dependencias de red — separado para poder probarlo sin una conexión
 * Baileys real.
 */

/** Extrae texto + tipo de medio (si lo hay) de un mensaje Baileys. No descarga bytes. */
export function extractMessageContent(waMessage) {
  const content = waMessage.message;
  if (!content) return { text: "", mediaKind: null };

  if (content.conversation) {
    return { text: content.conversation, mediaKind: null };
  }
  if (content.extendedTextMessage?.text) {
    return { text: content.extendedTextMessage.text, mediaKind: null };
  }
  if (content.imageMessage) {
    return { text: content.imageMessage.caption || "", mediaKind: "image", mimetype: content.imageMessage.mimetype };
  }
  if (content.documentMessage) {
    return {
      text: content.documentMessage.caption || content.documentMessage.fileName || "",
      mediaKind: "document", mimetype: content.documentMessage.mimetype,
    };
  }
  if (content.audioMessage) {
    return { text: "", mediaKind: "audio", mimetype: content.audioMessage.mimetype };
  }
  return { text: "", mediaKind: null };
}

/** Normaliza un JID de Baileys (ej: "5215512345678@s.whatsapp.net") a un sender_id simple. */
export function jidToSenderId(jid) {
  return (jid || "").split("@")[0];
}

/** Construye el payload canónico para POST /api/v1/comms/inbound a partir de un mensaje Baileys. */
export function toInboundPayload(waMessage, botJid) {
  const { text, mediaKind, mimetype } = extractMessageContent(waMessage);
  const metadata = {};
  if (mediaKind) {
    metadata.media_kind = mediaKind;
    metadata.mimetype = mimetype;
    metadata.note = "Descarga diferida: F3-T5 la resuelve vía Storage/OCR/STT (F3-T6).";
  }
  return {
    provider: "whatsapp",
    sender_id: jidToSenderId(waMessage.key.remoteJid),
    recipient_id: jidToSenderId(botJid),
    text,
    message_id: waMessage.key.id,
    metadata,
  };
}
