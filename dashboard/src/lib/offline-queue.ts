// Cola de sincronización offline-first (F4-T3): si `sendInbound` falla por falta de red (no por
// un error real del Gateway), la captura se guarda aquí en IndexedDB en vez de perderse, y se
// reintenta sola al volver la conexión. IndexedDB (no localStorage) porque el payload puede
// incluir una foto/audio en base64 -- potencialmente varios MB, fuera del límite práctico de
// localStorage (~5MB) y bloqueante por ser síncrono.
import { sendInbound, type InboundMessageInput } from "./api-client";

const DB_NAME = "mindos-offline-queue";
const STORE_NAME = "captures";
const DB_VERSION = 1;

export interface QueuedCapture extends InboundMessageInput {
  id: string;
  queuedAt: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function withStore<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const request = fn(tx.objectStore(STORE_NAME));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

export async function enqueueCapture(input: InboundMessageInput): Promise<QueuedCapture> {
  const item: QueuedCapture = { ...input, id: crypto.randomUUID(), queuedAt: new Date().toISOString() };
  await withStore("readwrite", (store) => store.add(item));
  return item;
}

export async function listQueuedCaptures(): Promise<QueuedCapture[]> {
  return withStore("readonly", (store) => store.getAll());
}

export async function removeQueuedCapture(id: string): Promise<void> {
  await withStore("readwrite", (store) => store.delete(id));
}

/** Reintenta cada captura pendiente contra el Gateway; las que fallan (sigue sin haber red) se quedan en cola. */
export async function flushQueuedCaptures(): Promise<{ sent: number; failed: number }> {
  const pending = await listQueuedCaptures();
  let sent = 0;
  let failed = 0;
  for (const item of pending) {
    try {
      await sendInbound(item);
      await removeQueuedCapture(item.id);
      sent += 1;
    } catch {
      failed += 1;
    }
  }
  return { sent, failed };
}
