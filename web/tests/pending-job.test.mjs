import { test } from "node:test";
import assert from "node:assert/strict";
import { loadTs } from "./helpers/load-ts.mjs";
const { readPending, writePending } = loadTs("src/lib/pending-job.ts");
function storage() {
  const values = new Map();
  return { values, getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
}
test("refresh recovery keeps only the accepted receipt, never the original upload", () => {
  const target = storage();
  const job = { id: "a".repeat(32), myLang: "ml-IN", submittedAt: 123, audio: "private", transcript: "private" };
  assert.equal(writePending(job, target), true);
  assert.deepEqual(readPending(target), { id: job.id, myLang: job.myLang, submittedAt: 123 });
  assert.equal([...target.values.values()].join("").includes("private"), false);
  writePending(null, target);
  assert.equal(readPending(target), null);
});
test("unavailable session storage is reported without crashing", () => {
  const denied = { getItem() { throw new Error(); }, setItem() { throw new Error(); }, removeItem() { throw new Error(); } };
  assert.equal(writePending({ id: "a".repeat(32), myLang: "en-IN", submittedAt: 1 }, denied), false);
  assert.equal(readPending(denied), null);
});

test("conversation recovery retains just the pair and active speaker, never messages or participant names", () => {
  const target = storage();
  const conversation = { a: "hi-IN", b: "ml-IN", speaker: "b", transcript: "private words", personName: "private name" };
  writePending({ id: "b".repeat(32), myLang: "hi-IN", submittedAt: 20, conversation, messages: ["private"] }, target);
  assert.deepEqual(readPending(target).conversation, { a: "hi-IN", b: "ml-IN", speaker: "b" });
  assert.equal([...target.values.values()].join("").includes("private"), false);
});

test("only known demonstration IDs survive recovery", () => {
  const target = storage();
  const job = { id: "c".repeat(32), myLang: "en-IN", submittedAt: 20, demo: "college" };
  writePending(job, target); assert.equal(readPending(target).demo, "college");
  writePending({ ...job, demo: "private message" }, target); assert.equal(readPending(target).demo, undefined);
});

test("a corrupt conversation target cannot mislabel a recovered translation", () => {
  const target = storage();
  writePending({ id: "d".repeat(32), myLang: "hi-IN", submittedAt: 20,
    conversation: { a: "en-IN", b: "bn-IN", speaker: "a" } }, target);
  assert.equal(readPending(target).conversation, undefined);
  assert.equal(readPending(target).myLang, "hi-IN");
});
