import { test } from "node:test";
import assert from "node:assert/strict";
import { loadTs } from "./helpers/load-ts.mjs";
const { direction, otherSpeaker, canHandOff, turnFromNote, isConversation } = loadTs("src/lib/conversation.ts");

const config = { a: "en-IN", b: "hi-IN", speaker: "a" };
const result = { detected_lang: "en-IN", transcript: "Do not pay ₹500 before Friday.", translation: "शुक्रवार से पहले ₹500 मत दीजिए।",
  same_language: false, my_lang: "hi-IN", missing_facts: [], speech_live: true, translation_live: true };

test("turn direction swaps both languages without reading a changed preference", () => {
  assert.deepEqual(direction(config), { from: "en-IN", to: "hi-IN" });
  assert.deepEqual(direction({ ...config, speaker: otherSpeaker(config.speaker) }), { from: "hi-IN", to: "en-IN" });
  assert.equal(otherSpeaker(otherSpeaker("a")), "a");
});
test("handoff needs an explicit check and a current translation of the exact edited words", () => {
  const turn = turnFromNote(result, config);
  assert.equal(canHandOff(turn, turn.text, turn.from, false), false);
  assert.equal(canHandOff(turn, turn.text, turn.from, true), true);
  assert.equal(canHandOff(turn, turn.text.replace("500", "600"), turn.from, true), false);
  assert.equal(canHandOff(turn, turn.text, "bn-IN", true), false);
  assert.equal(canHandOff({ ...turn, live: false }, turn.text, turn.from, true), false);
  assert.equal(canHandOff({ ...turn, translation: "" }, turn.text, turn.from, true), false);
});
test("recorded results preserve negation, amounts and missing-detail warnings without shortening", () => {
  const text = result.transcript.repeat(100);
  const turn = turnFromNote({ ...result, transcript: text, missing_facts: ["₹500"] }, config);
  assert.equal(turn.text, text);
  assert.equal(turn.translation, result.translation);
  assert.deepEqual(turn.missing, ["₹500"]);
  assert.equal(turn.speaker, "a");
});
test("same-language turns use the original text; canned speech is never passed off as a live turn", () => {
  const same = turnFromNote({ ...result, same_language: true, translation: null }, { ...config, b: "en-IN" });
  assert.equal(same.translation, result.transcript);
  assert.equal(turnFromNote({ ...result, speech_live: false }, config).live, false);
  assert.equal(turnFromNote({ ...result, translation_live: false }, config).live, false);
  assert.equal(turnFromNote({ ...result, my_lang: "bn-IN" }, config).live, false);
});
test("conversation configuration accepts supported language pairs and rejects corrupt receipts", () => {
  assert.equal(isConversation(config), true);
  assert.equal(isConversation({ ...config, a: "xx-XX" }), false);
  assert.equal(isConversation({ ...config, speaker: "other" }), false);
  assert.equal(isConversation(null), false);
});
