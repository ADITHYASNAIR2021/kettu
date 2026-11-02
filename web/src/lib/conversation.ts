import { isLang, type LangCode } from "./languages";
import type { NoteResult } from "./api";

export type Speaker = "a" | "b";
export type ConversationConfig = { a: LangCode; b: LangCode; speaker: Speaker };
export type ConversationTurn = { id: string; speaker: Speaker; from: LangCode; to: LangCode;
  text: string; translation: string; missing: string[]; live: boolean };
export function isConversation(value: unknown): value is ConversationConfig {
  const item = value as ConversationConfig | null;
  return Boolean(item && isLang(item.a) && isLang(item.b) && (item.speaker === "a" || item.speaker === "b"));
}
export function direction(config: ConversationConfig) {
  return config.speaker === "a" ? { from: config.a, to: config.b } : { from: config.b, to: config.a };
}
export function otherSpeaker(speaker: Speaker): Speaker { return speaker === "a" ? "b" : "a"; }
export function turnFromNote(result: NoteResult, config: ConversationConfig): ConversationTurn {
  const { from, to } = direction(config);
  return { id: crypto.randomUUID(), speaker: config.speaker, from: result.detected_lang ?? from, to,
    text: result.transcript, translation: result.same_language ? result.transcript : result.translation ?? "",
    missing: result.missing_facts, live: result.my_lang === to && result.speech_live !== false && (result.same_language || result.translation_live !== false) };
}
export function canHandOff(turn: ConversationTurn | null, text: string, from: LangCode, checked: boolean): boolean {
  return Boolean(turn && checked && turn.live && text.trim() && turn.translation.trim() && turn.text === text && turn.from === from);
}
