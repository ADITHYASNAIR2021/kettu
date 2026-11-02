import { readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
async function files(folder) {
  const entries = await readdir(folder, { withFileTypes: true });
  return (await Promise.all(entries.map((entry) => entry.isDirectory()
    ? files(path.join(folder, entry.name)) : [path.join(folder, entry.name)]))).flat();
}
const staticRoot = path.join(root, ".next", "static");
const assets = (await files(staticRoot)).filter((file) => /\.(?:js|css|woff2)$/.test(file))
  .map((file) => "/_next/static/" + path.relative(staticRoot, file).split(path.sep).join("/")).sort();
const buildId = (await readFile(path.join(root, ".next", "BUILD_ID"), "utf8")).trim();
if (!buildId || !assets.some((url) => url.endsWith(".js"))) throw new Error("Build the app before generating its offline worker.");
const precache = ["/", "/privacy", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png", ...assets];
const template = await readFile(path.join(root, "src", "pwa", "worker.js"), "utf8");
const worker = template.replace('"__BUILD_ID__"', JSON.stringify(buildId)).replace('["__PRECACHE__"]', JSON.stringify(precache));
await writeFile(path.join(root, "public", "pwa-worker.js"), worker);
await writeFile(path.join(root, "public", "pwa-assets.json"), JSON.stringify({ buildId, assets: precache }));
process.stdout.write(`Offline worker: ${precache.length} public assets, build ${buildId}\n`);
