import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { createApp } from "../src/app.js";

let server;
let baseUrl;
let sentMessages;
let sockConnected;

function fakeWaClient() {
  return {
    getSock: () => (sockConnected ? { sendMessage: async (jid, content) => { sentMessages.push({ jid, content }); } } : null),
    isConnected: () => sockConnected,
  };
}

before(async () => {
  sentMessages = [];
  sockConnected = true;
  const app = createApp(fakeWaClient(), null);
  server = app.listen(0);
  await new Promise((resolve) => server.once("listening", resolve));
  baseUrl = `http://localhost:${server.address().port}`;
});

after(() => {
  server.close();
});

test("GET /health reports ok and connected when the socket is up", async () => {
  const res = await fetch(`${baseUrl}/health`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "ok");
  assert.equal(body.connected, true);
  assert.equal(body.service, "whatsapp");
});

test("POST /send delivers via the active socket", async () => {
  const res = await fetch(`${baseUrl}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipient_id: "5215512345678", text: "hola" }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.status, "sent");

  assert.equal(sentMessages.length, 1);
  assert.equal(sentMessages[0].jid, "5215512345678@s.whatsapp.net");
  assert.equal(sentMessages[0].content.text, "hola");
});

test("POST /send rejects a request missing required fields", async () => {
  const res = await fetch(`${baseUrl}/send`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipient_id: "5215512345678" }),
  });
  assert.equal(res.status, 422);
});

test("GET /health and POST /send report degraded/503 when not connected", async () => {
  sockConnected = false;
  try {
    const health = await fetch(`${baseUrl}/health`);
    assert.equal((await health.json()).status, "degraded");

    const send = await fetch(`${baseUrl}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_id: "5215512345678", text: "hola" }),
    });
    assert.equal(send.status, 503);
  } finally {
    sockConnected = true;
  }
});
