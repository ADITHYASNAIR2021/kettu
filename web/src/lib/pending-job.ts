import { isLang, type LangCode } from "./languages";
import { direction, isConversation, type ConversationConfig } from "./conversation";

const KEY = "kettu:pending-job:v1";
export type PendingJob = { id: string; myLang: LangCode; submittedAt: number; conversation?: ConversationConfig; demo?: string };

export function readPending(storage?: Pick<Storage, "getItem" | "removeItem">): PendingJob | null {
  try {
    storage = storage ?? sessionStorage;
    const raw = storage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!value || typeof value.id !== "string" || !/^[a-f0-9]{32}$/.test(value.id) || !isLang(value.myLang) || !Number.isFinite(value.submittedAt)) {
      storage.removeItem(KEY); return null;
    }
    return { id: value.id, myLang: value.myLang, submittedAt: value.submittedAt,
      ...(isConversation(value.conversation) && direction(value.conversation).to === value.myLang ? { conversation: { a: value.conversation.a, b: value.conversation.b, speaker: value.conversation.speaker } } : {}),
      ...(["site", "college", "weekend"].includes(value.demo) ? { demo: value.demo } : {}) };
  } catch { return null; }
}

export function writePending(job: PendingJob | null, storage?: Pick<Storage, "setItem" | "removeItem">): boolean {
  try {
    storage = storage ?? sessionStorage;
    if (job) storage.setItem(KEY, JSON.stringify({ id: job.id, myLang: job.myLang, submittedAt: job.submittedAt,
      ...(isConversation(job.conversation) && direction(job.conversation).to === job.myLang ? { conversation: { a: job.conversation.a, b: job.conversation.b, speaker: job.conversation.speaker } } : {}),
      ...(["site", "college", "weekend"].includes(job.demo ?? "") ? { demo: job.demo } : {}) }));
    else storage.removeItem(KEY);
    return true;
  } catch { return false; }
}
