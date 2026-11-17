import { readFile, writeFile, mkdir, stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(
  await readFile(path.join(root, "config.json"), "utf8"),
);
await mkdir(path.join(root, "models"), { recursive: true });
for (const item of Object.values(config.models)) {
  const target = path.join(root, "models", item.file);
  let bytes;
  try {
    bytes = await readFile(target);
  } catch {}
  if (!bytes) {
    const url =
      "https://github.com/PedroFlores199/AutoPeritaje/releases/download/models-v1/" +
      item.file;
    const response = await fetch(url);
    if (!response.ok)
      throw new Error("Model download failed: HTTP " + response.status);
    const chunks = [];
    let total = 0;
    for await (const chunk of response.body) {
      total += chunk.length;
      if (total > item.bytes) throw new Error("Model exceeds expected size");
      chunks.push(chunk);
    }
    bytes = Buffer.concat(chunks);
    if (
      bytes.length !== item.bytes ||
      createHash("sha256").update(bytes).digest("hex") !== item.sha256
    )
      throw new Error("Model checksum mismatch");
    await writeFile(target, bytes);
  }
  if (
    bytes.length !== item.bytes ||
    createHash("sha256").update(bytes).digest("hex") !== item.sha256
  )
    throw new Error("Existing model checksum mismatch");
  console.log(item.file + ": verified " + (await stat(target)).size + " bytes");
}
