import type { ActionItem } from "./api";
import { isLang, type LangCode } from "./languages";

export const CARD_FIELDS = ["task", "quantity", "person", "deadline"] as const;
export type CardField = typeof CARD_FIELDS[number];
export type DraftAction = ActionItem & { id: string; completed: boolean; edited: boolean };
export type CardAction = Record<CardField, string> & { id: string; completed: boolean };
export type SavedCard = {
  version: 1; id: string; title: string; language: LangCode; sourceLanguage: LangCode | null;
  actions: CardAction[]; createdAt: number; updatedAt: number;
};
export type ReplySeed = { text: string; from: LangCode; to: LangCode };

export function draftActions(items: ActionItem[]): DraftAction[] {
  return items.map((item, index) => ({ ...item, id: `suggested-${index}`, completed: false, edited: false }));
}

export function cardActions(items: DraftAction[]): CardAction[] {
  return items.filter((item) => item.task.value.trim()).map((item) => ({
    id: item.id, completed: item.completed, task: item.task.value,
    quantity: item.quantity.value, person: item.person.value, deadline: item.deadline.value,
  }));
}

export function editableActions(items: CardAction[]): DraftAction[] {
  return items.map((item) => ({ id: item.id, completed: item.completed, edited: true,
    task: { value: item.task, source_text: "" }, quantity: { value: item.quantity, source_text: "" },
    person: { value: item.person, source_text: "" }, deadline: { value: item.deadline, source_text: "" } }));
}

/** A whitelist projection: never persist a transcript, audio, quote or arbitrary extra properties. */
export function cleanCard(value: SavedCard): SavedCard {
  if (!value || value.version !== 1 || typeof value.id !== "string" || !/^[\w-]{1,80}$/.test(value.id)
      || typeof value.title !== "string" || !value.title.trim() || value.title.length > 80
      || !isLang(value.language) || (value.sourceLanguage !== null && !isLang(value.sourceLanguage))
      || !Number.isFinite(value.createdAt) || !Number.isFinite(value.updatedAt)
      || !Array.isArray(value.actions) || !value.actions.length || value.actions.length > 8) throw new Error("invalid_card");
  if (new Set(value.actions.map((item) => item?.id)).size !== value.actions.length) throw new Error("invalid_card");
  const actions = value.actions.map((item) => {
    if (!item || typeof item.id !== "string" || item.id.length > 80 || !item.id || typeof item.completed !== "boolean"
      || CARD_FIELDS.some((field) => typeof item[field] !== "string" || item[field].length > 300)
      || !item.task.trim()) throw new Error("invalid_card");
    return { id: item.id, completed: item.completed, task: item.task,
      quantity: item.quantity, person: item.person, deadline: item.deadline };
  });
  return { version: 1, id: value.id, title: value.title.trim(), language: value.language,
    sourceLanguage: value.sourceLanguage, actions, createdAt: value.createdAt, updatedAt: value.updatedAt };
}

export function makeCard(actions: DraftAction[], language: LangCode, sourceLanguage: LangCode | null, title: string, previous?: SavedCard): SavedCard {
  const now = Date.now();
  return cleanCard({ version: 1, id: previous?.id ?? crypto.randomUUID(), title, language, sourceLanguage,
    actions: cardActions(actions), createdAt: previous?.createdAt ?? now, updatedAt: now });
}

export function cardText(card: SavedCard, labels: Record<CardField, string>): string {
  return card.title + "\n\n" + card.actions.map((item) => `${item.completed ? "☑" : "☐"} ${item.task}`
    + CARD_FIELDS.slice(1).filter((field) => item[field]).map((field) => `\n${labels[field]}: ${item[field]}`).join("")).join("\n\n");
}
