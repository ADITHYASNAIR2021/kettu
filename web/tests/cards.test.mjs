import { test, beforeEach } from "node:test";
import assert from "node:assert/strict";
import { IDBFactory } from "fake-indexeddb";
import { loadTs } from "./helpers/load-ts.mjs";

const cards = loadTs("src/lib/cards.ts");
const store = loadTs("src/lib/card-store.ts");
beforeEach(() => { globalThis.indexedDB = new IDBFactory(); });
function card(id = crypto.randomUUID()) {
  return { version: 1, id, title: "Delivery", language: "en-IN", sourceLanguage: "bn-IN", createdAt: 1, updatedAt: 2,
    actions: [{ id: "task-one", completed: true, task: "Keep gate open if delivery arrives", quantity: "60 bags", person: "", deadline: "Tomorrow, 8 AM" }] };
}

test("only edited card fields and independent checkmarks survive a storage round trip", async () => {
  const input = card();
  input.transcript = "DO NOT STORE transcript";
  input.audio = "DO NOT STORE recording";
  input.actions[0].source_text = "DO NOT STORE quotation";
  input.actions.push({ id: "task-two", completed: false, task: "Call the shop", quantity: "", person: "", deadline: "" });
  await store.saveCard(input);
  const [loaded] = await store.listCards();
  assert.equal(loaded.actions[0].quantity, "60 bags");
  assert.deepEqual(loaded.actions.map((item) => item.completed), [true, false]);
  assert.equal(loaded.actions[0].person, "");
  assert.equal(JSON.stringify(loaded).includes("DO NOT STORE"), false);
});

test("the 50-card limit is atomic; updating a saved card remains allowed", async () => {
  const saved = Array.from({ length: 50 }, () => card());
  await Promise.all(saved.map(store.saveCard));
  const results = await Promise.allSettled([store.saveCard(card()), store.saveCard(card())]);
  assert.ok(results.every((result) => result.status === "rejected" && result.reason.message === "cards_full"));
  await store.saveCard({ ...saved[0], title: "Changed", updatedAt: 10 });
  assert.equal((await store.listCards())[0].title, "Changed");
  assert.equal((await store.listCards()).length, 50);
});

test("deleting a card removes it without touching other cards", async () => {
  const first = card(), second = card();
  await store.saveCard(first); await store.saveCard(second); await store.deleteCard(first.id);
  assert.deepEqual((await store.listCards()).map((item) => item.id), [second.id]);
});

test("storage denial fails rather than claiming a successful save", async () => {
  globalThis.indexedDB = { open() { throw new Error("Access denied"); } };
  await assert.rejects(store.saveCard(card()));
  await assert.rejects(store.listCards());
});

test("invalid fields and duplicate task IDs cannot corrupt the card editor", () => {
  const input = card(); input.actions.push({ ...input.actions[0] });
  assert.throws(() => cards.cleanCard(input), /invalid_card/);
  input.actions = [{ ...input.actions[0], task: "x".repeat(301) }];
  assert.throws(() => cards.cleanCard(input), /invalid_card/);
});

test("saving a draft serializes edited values instead of model suggestions", () => {
  const details = (value) => ({ value, source_text: "raw words" });
  const draft = [{ id: "one", completed: true, edited: true, task: details("Bring cement"), quantity: details("60 bags"), person: details(""), deadline: details("tomorrow") }];
  const saved = cards.makeCard(draft, "en-IN", "bn-IN", "Edited card");
  assert.equal(saved.actions[0].quantity, "60 bags");
  assert.equal(JSON.stringify(saved).includes("raw words"), false);
});
