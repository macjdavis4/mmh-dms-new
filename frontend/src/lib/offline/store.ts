/**
 * The device's saved copy, in IndexedDB (the browser's own storage; no
 * library). One record. Wiped at sign-out, when someone else signs in, when
 * the feature is switched off, and after it expires.
 */
import { isExpired, type OfflinePack } from "./pack";

const DB = "mmh-offline";
const STORE = "packs";
const KEY = "units";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error ?? new Error("IndexedDB unavailable"));
  });
}

async function run<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  try {
    return await new Promise<T>((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const req = work(tx.objectStore(STORE));
      tx.oncomplete = () => resolve(req.result);
      tx.onerror = () => reject(tx.error ?? new Error("IndexedDB error"));
      tx.onabort = () => reject(tx.error ?? new Error("IndexedDB aborted"));
    });
  } finally {
    db.close();
  }
}

const available = () => typeof indexedDB !== "undefined";

export async function savePack(pack: OfflinePack): Promise<void> {
  if (!available()) return;
  await run("readwrite", (s) => s.put(pack, KEY));
}

/** The saved copy, or null if there is none or it has expired (then it's deleted). */
export async function loadPack(): Promise<OfflinePack | null> {
  if (!available()) return null;
  try {
    const pack = (await run("readonly", (s) => s.get(KEY))) as OfflinePack | undefined;
    if (!pack) return null;
    if (isExpired(pack)) {
      await clearPack();
      return null;
    }
    return pack;
  } catch {
    return null;
  }
}

export async function clearPack(): Promise<void> {
  if (!available()) return;
  try {
    await run("readwrite", (s) => s.delete(KEY));
  } catch {
    // nothing saved, or storage blocked: nothing to wipe
  }
}
