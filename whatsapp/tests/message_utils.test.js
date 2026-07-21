import assert from "node:assert/strict";
import { test } from "node:test";
import { extractMessageContent, jidToSenderId, toInboundPayload } from "../src/message_utils.js";

test("extractMessageContent reads plain conversation text", () => {
  const result = extractMessageContent({ message: { conversation: "hola mundo" } });
  assert.equal(result.text, "hola mundo");
  assert.equal(result.mediaKind, null);
});

test("extractMessageContent reads extended text messages (replies/links)", () => {
  const result = extractMessageContent({ message: { extendedTextMessage: { text: "una respuesta" } } });
  assert.equal(result.text, "una respuesta");
  assert.equal(result.mediaKind, null);
});

test("extractMessageContent flags image messages with their caption", () => {
  const result = extractMessageContent({
    message: { imageMessage: { caption: "mira esto", mimetype: "image/jpeg" } },
  });
  assert.equal(result.text, "mira esto");
  assert.equal(result.mediaKind, "image");
  assert.equal(result.mimetype, "image/jpeg");
});

test("extractMessageContent flags document messages, falling back to filename", () => {
  const result = extractMessageContent({
    message: { documentMessage: { fileName: "informe.pdf", mimetype: "application/pdf" } },
  });
  assert.equal(result.text, "informe.pdf");
  assert.equal(result.mediaKind, "document");
});

test("extractMessageContent returns empty text for unsupported message shapes", () => {
  const result = extractMessageContent({ message: { stickerMessage: {} } });
  assert.equal(result.text, "");
  assert.equal(result.mediaKind, null);
});

test("extractMessageContent handles a message with no content gracefully", () => {
  const result = extractMessageContent({ message: null });
  assert.equal(result.text, "");
  assert.equal(result.mediaKind, null);
});

test("jidToSenderId strips the WhatsApp domain suffix", () => {
  assert.equal(jidToSenderId("5215512345678@s.whatsapp.net"), "5215512345678");
});

test("jidToSenderId handles an empty/undefined jid without throwing", () => {
  assert.equal(jidToSenderId(undefined), "");
});

test("toInboundPayload builds the canonical shape expected by POST /api/v1/comms/inbound", () => {
  const waMessage = {
    key: { remoteJid: "5215512345678@s.whatsapp.net", id: "ABC123", fromMe: false },
    message: { conversation: "El puerto configurado es 443." },
  };
  const payload = toInboundPayload(waMessage, "5219998887777@s.whatsapp.net");

  assert.equal(payload.provider, "whatsapp");
  assert.equal(payload.sender_id, "5215512345678");
  assert.equal(payload.recipient_id, "5219998887777");
  assert.equal(payload.text, "El puerto configurado es 443.");
  assert.equal(payload.message_id, "ABC123");
  assert.deepEqual(payload.metadata, {});
});

test("toInboundPayload annotates media messages in metadata for the pipeline (F3-T5) to resolve", () => {
  const waMessage = {
    key: { remoteJid: "5215512345678@s.whatsapp.net", id: "ABC124", fromMe: false },
    message: { imageMessage: { caption: "", mimetype: "image/png" } },
  };
  const payload = toInboundPayload(waMessage, "5219998887777@s.whatsapp.net");

  assert.equal(payload.metadata.media_kind, "image");
  assert.equal(payload.metadata.mimetype, "image/png");
});
