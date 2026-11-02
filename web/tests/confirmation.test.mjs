import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { loadTs } from "./helpers/load-ts.mjs";
const { confirmationText, CONFIRM_LABELS } = loadTs("src/lib/confirmation.ts");
const fixtures = JSON.parse(await readFile(new URL("fixtures/communication.json", import.meta.url), "utf8"));
for (const fixture of fixtures) test(`${fixture.id}: exact facts, conditions and negation survive confirmation drafting`, () => {
  const action = { ...fixture, id: "one", completed: false };
  const output = confirmationText([action], { one: ["task", "quantity", "person", "deadline"] }, fixture.language);
  for (const field of ["task", "quantity", "person", "deadline"]) if (fixture[field]) assert.ok(output.includes(fixture[field]));
  if (!fixture.person) assert.equal(output.includes(CONFIRM_LABELS[fixture.language].person + ":"), false);
});
test("changing preferences cannot change the card's declared source language", () => {
  const output = confirmationText([{ id: "one", task: "६० बोरी", quantity: "", person: "", deadline: "", completed: false }], { one: ["task"] }, "hi-IN");
  assert.ok(output.startsWith(CONFIRM_LABELS["hi-IN"].intro));
  assert.equal(output.startsWith(CONFIRM_LABELS["en-IN"].intro), false);
});
test("overlong drafts retain their last fact instead of silently truncating it", () => {
  const actions = Array.from({ length: 8 }, (_, index) => ({ id: String(index), task: "x".repeat(290), quantity: "₹12500", person: "", deadline: "Friday", completed: false }));
  const output = confirmationText(actions, Object.fromEntries(actions.map((item) => [item.id, ["task", "quantity", "deadline"]])), "en-IN");
  assert.ok(output.length > 700 && output.endsWith("Friday"));
});
