import { isLang, type LangCode } from "./languages";
import type { Voice } from "./api";
import type { UiLang } from "./i18n";

export type Prefs = {
  myLang: LangCode | null;
  uiLang: UiLang;
  voice: Voice;
  keyterms: string[];
  consented: boolean;
};

const KEY = "kettu:prefs:v1";
const DEVICE_KEY = "kettu:device:v1";

export const DEFAULT_PREFS: Prefs = { myLang: null, uiLang: "en", voice: "female", keyterms: [], consented: false };

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: prefs last for this visit only */
  }
}

export function loadPrefs(): Prefs {
  const raw = safeGet(KEY);
  if (!raw) return { ...DEFAULT_PREFS };
  try {
    const p = JSON.parse(raw);
    return {
      myLang: isLang(p.myLang) ? p.myLang : null,
      uiLang: ["en", "ml", "hi", "bn"].includes(p.uiLang) ? p.uiLang : "en",
      voice: p.voice === "male" ? "male" : "female",
      keyterms: Array.isArray(p.keyterms) ? p.keyterms.filter((k: unknown) => typeof k === "string").slice(0, 50) : [],
      consented: Boolean(p.consented),
    };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

export function savePrefs(p: Prefs) {
  safeSet(KEY, JSON.stringify(p));
}

/** Random id kept on this phone only. Not tied to a phone number or account. */
export function deviceId(): string {
  let id = safeGet(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    safeSet(DEVICE_KEY, id);
  }
  return id;
}

/** Suggest an interface language from the reading language. */
export function uiFor(code: LangCode): UiLang {
  const base = code.split("-")[0];
  return base === "ml" || base === "hi" || base === "bn" ? base : "en";
}
