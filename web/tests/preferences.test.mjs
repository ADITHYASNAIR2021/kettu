import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { loadTs } from "./helpers/load-ts.mjs";
const { loadPrefs, savePrefs } = loadTs("src/lib/prefs.ts");
afterEach(() => { delete globalThis.localStorage; });
test("sound feedback stays off for new and existing preferences until explicitly enabled", () => {
  let value = null;
  globalThis.localStorage = { getItem: () => value, setItem: (_, saved) => { value = saved; } };
  assert.equal(loadPrefs().sounds, false);
  value = JSON.stringify({ myLang: "en-IN", consented: true });
  assert.equal(loadPrefs().sounds, false);
  savePrefs({ ...loadPrefs(), sounds: true });
  assert.equal(loadPrefs().sounds, true);
  value = JSON.stringify({ sounds: "true" });
  assert.equal(loadPrefs().sounds, false);
});
