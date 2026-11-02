import ts from "typescript";
import vm from "node:vm";
import path from "node:path";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const cache = new Map();
const nativeRequire = createRequire(import.meta.url);
export function loadTs(filename) {
  filename = path.resolve(filename);
  if (cache.has(filename)) return cache.get(filename).exports;
  const loadedModule = { exports: {} };
  cache.set(filename, loadedModule);
  const code = ts.transpileModule(readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 }, fileName: filename,
  }).outputText;
  const wrapper = vm.runInThisContext(`(function(exports, require, module){${code}\n})`, { filename });
  wrapper(loadedModule.exports, (name) => name.startsWith(".")
    ? loadTs(path.resolve(path.dirname(filename), name.endsWith(".ts") ? name : name + ".ts")) : nativeRequire(name), loadedModule);
  return loadedModule.exports;
}
