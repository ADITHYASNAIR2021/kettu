import { isLang, type LangCode } from "./languages";

const KEY = "kettu:pending-job:v1";
export type PendingJob = { id: string; myLang: LangCode; submittedAt: number };

export function readPending(storage?: Pick<Storage, "getItem" | "removeItem">): PendingJob | null {
  try {
    storage = storage ?? sessionStorage;
    const raw = storage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value.id !== "string" || !/^[a-f0-9]{32}$/.test(value.id) || !isLang(value.myLang) || !Number.isFinite(value.submittedAt)) {
      storage.removeItem(KEY); return null;
    }
    return { id: value.id, myLang: value.myLang, submittedAt: value.submittedAt };
  } catch { return null; }
}

export function writePending(job: PendingJob | null, storage?: Pick<Storage, "setItem" | "removeItem">): boolean {
  try {
    storage = storage ?? sessionStorage;
    if (job) storage.setItem(KEY, JSON.stringify({ id: job.id, myLang: job.myLang, submittedAt: job.submittedAt }));
    else storage.removeItem(KEY);
    return true;
  } catch { return false; }
}
