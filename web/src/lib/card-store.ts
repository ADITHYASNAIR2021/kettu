import { cleanCard, type SavedCard } from "./cards";

export const MAX_CARDS = 50;
const DB_NAME = "kettu-device-cards";
const STORE = "cards";

async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    let blocked = false;
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => { request.result.createObjectStore(STORE, { keyPath: "id" }); };
    request.onerror = () => reject(new Error("storage_failed"));
    request.onblocked = () => { blocked = true; reject(new Error("storage_failed")); };
    request.onsuccess = () => {
      if (blocked) { request.result.close(); return; }
      request.result.onversionchange = () => request.result.close();
      resolve(request.result);
    };
  });
}

export async function listCards(): Promise<SavedCard[]> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const transaction = db.transaction(STORE, "readonly");
      const request = transaction.objectStore(STORE).getAll();
      transaction.oncomplete = () => {
        try { resolve(request.result.map(cleanCard).sort((a, b) => b.updatedAt - a.updatedAt)); }
        catch { reject(new Error("storage_failed")); }
      };
      transaction.onerror = transaction.onabort = () => reject(new Error("storage_failed"));
    });
  } finally { db.close(); }
}

export async function saveCard(input: SavedCard): Promise<void> {
  const card = cleanCard(input);
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      const store = transaction.objectStore(STORE);
      let full = false;
      const existing = store.get(card.id);
      existing.onsuccess = () => {
        const count = store.count();
        count.onsuccess = () => {
          if (!existing.result && count.result >= MAX_CARDS) { full = true; transaction.abort(); }
          else store.put(card);
        };
      };
      transaction.oncomplete = () => resolve();
      transaction.onerror = transaction.onabort = () => reject(new Error(full ? "cards_full" : "storage_failed"));
    });
  } finally { db.close(); }
}

export async function deleteCard(id: string): Promise<void> {
  const db = await database();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE, "readwrite");
      transaction.objectStore(STORE).delete(id);
      transaction.oncomplete = () => resolve();
      transaction.onerror = transaction.onabort = () => reject(new Error("storage_failed"));
    });
  } finally { db.close(); }
}
