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
