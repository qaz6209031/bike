/** Lossless EXT_meshopt_compression: no quantization, filters, or geometry/node reordering. */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, rename, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { MeshoptDecoder, MeshoptEncoder } from "meshoptimizer";

const EXTENSION = "EXT_meshopt_compression";
type MeshoptView = { buffer: number; byteOffset?: number; byteLength: number; byteStride: number; count: number; mode: "ATTRIBUTES" | "INDICES"; filter?: string };
type BufferView = { buffer: number; byteOffset?: number; byteLength: number; byteStride?: number; extensions?: Record<string, unknown> & { EXT_meshopt_compression?: MeshoptView } };
type Accessor = { bufferView?: number; byteOffset?: number; count: number; componentType: number; type: string; sparse?: unknown };
export type GlbDocument = {
  buffers: { byteLength: number; uri?: string; extensions?: Record<string, unknown> }[];
  bufferViews: BufferView[];
  accessors: Accessor[];
  meshes: { primitives: { indices?: number; attributes?: Record<string, number> }[] }[];
  extensionsUsed?: string[];
  extensionsRequired?: string[];
  [key: string]: unknown;
};

export function readGlb(file: Buffer): { document: GlbDocument; binary: Buffer } {
  assert.ok(file.length >= 28, "GLB is truncated");
  assert.equal(file.readUInt32LE(0), 0x46546c67, "Expected a GLB file");
  assert.equal(file.readUInt32LE(4), 2, "Expected glTF 2.0");
  assert.equal(file.readUInt32LE(8), file.length, "GLB length mismatch");
  assert.equal(file.readUInt32LE(16), 0x4e4f534a, "Expected a JSON chunk");
  const jsonEnd = 20 + file.readUInt32LE(12);
  assert.ok(jsonEnd + 8 <= file.length, "GLB JSON chunk is truncated");
  assert.equal(file.readUInt32LE(jsonEnd + 4), 0x004e4942, "Expected a BIN chunk");
  assert.equal(jsonEnd + 8 + file.readUInt32LE(jsonEnd), file.length, "GLB BIN chunk length mismatch");
  return { document: JSON.parse(file.subarray(20, jsonEnd).toString()), binary: file.subarray(jsonEnd + 8) };
}

export function writeGlb(document: GlbDocument, binary: Buffer): Buffer {
  const json = Buffer.from(JSON.stringify(document));
  const jsonPadding = Buffer.alloc((4 - json.length % 4) % 4, 32);
  const binPadding = Buffer.alloc((4 - binary.length % 4) % 4);
  const header = Buffer.alloc(20);
  header.writeUInt32LE(0x46546c67, 0);
  header.writeUInt32LE(2, 4);
  header.writeUInt32LE(28 + json.length + jsonPadding.length + binary.length + binPadding.length, 8);
  header.writeUInt32LE(json.length + jsonPadding.length, 12);
  header.writeUInt32LE(0x4e4f534a, 16);
  const binHeader = Buffer.alloc(8);
  binHeader.writeUInt32LE(binary.length + binPadding.length, 0);
  binHeader.writeUInt32LE(0x004e4942, 4);
  return Buffer.concat([header, json, jsonPadding, binHeader, binary, binPadding]);
}

function slice(binary: Buffer, offset: number, length: number) {
  assert.ok(offset >= 0 && length > 0 && offset + length <= binary.length, "Buffer view is outside the BIN chunk");
  return binary.subarray(offset, offset + length);
}

/** Also used by asset tests, which inspect the original float32 coordinates after decoding. */
export async function decodeBufferViews(glb: ReturnType<typeof readGlb>): Promise<Buffer[]> {
  await MeshoptDecoder.ready;
  return glb.document.bufferViews.map((view) => {
    const extension = view.extensions?.EXT_meshopt_compression;
    if (!extension) {
      assert.equal(view.buffer, 0, "Expected an embedded buffer view");
      return slice(glb.binary, view.byteOffset ?? 0, view.byteLength);
    }
    assert.equal(extension.buffer, 0, "Expected embedded compressed data");
    assert.equal(extension.count * extension.byteStride, view.byteLength);
    const decoded = Buffer.alloc(view.byteLength);
    MeshoptDecoder.decodeGltfBuffer(decoded, extension.count, extension.byteStride,
      slice(glb.binary, extension.byteOffset ?? 0, extension.byteLength), extension.mode, extension.filter);
    return decoded;
  });
}

export async function compressGlb(file: Buffer): Promise<Buffer> {
  const original = readGlb(file);
  // Re-running the command must not recompress or alter an already compressed export.
  if (original.document.extensionsUsed?.includes(EXTENSION)) return file;
  assert.equal(original.document.buffers.length, 1, "Expected a self-contained Blender GLB");
  assert.ok(!original.document.buffers[0].uri, "External buffers are unsupported");
  await Promise.all([MeshoptEncoder.ready, MeshoptDecoder.ready]);
  const originalViews = await decodeBufferViews(original);
  const document = structuredClone(original.document);
  const indices = new Set(document.meshes.flatMap((mesh) => mesh.primitives.flatMap((p) => p.indices === undefined ? [] : [p.indices])));
  const accessorsByView = new Map<number, { accessor: Accessor; index: number }[]>();
  document.accessors.forEach((accessor, index) => {
    if (accessor.bufferView === undefined) return;
    const entries = accessorsByView.get(accessor.bufferView) ?? [];
    entries.push({ accessor, index });
    accessorsByView.set(accessor.bufferView, entries);
  });
  const components: Record<string, number> = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4 };
  const widths: Record<number, number> = { 5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4 };
  const payloads: Buffer[] = [];
  let byteOffset = 0;
  let compressedViews = 0;
  document.bufferViews.forEach((view, index) => {
    const source = originalViews[index];
    const entries = accessorsByView.get(index) ?? [];
    let payload = source;
    // Preserve images and unfamiliar/interleaved layouts verbatim instead of guessing their layout.
    if (entries.length === 1) {
      const { accessor, index: accessorIndex } = entries[0];
      const stride = view.byteStride ?? components[accessor.type] * widths[accessor.componentType];
      const mode = indices.has(accessorIndex) ? "INDICES" : "ATTRIBUTES";
      const validStride = mode === "INDICES" ? stride === 2 || stride === 4 : stride > 0 && stride <= 256 && stride % 4 === 0;
      if (validStride && !accessor.sparse && !(accessor.byteOffset ?? 0) && accessor.count * stride === source.length) {
        // INDICES preserves every index, including triangle vertex order; TRIANGLES may rotate it.
        const encoded = MeshoptEncoder.encodeGltfBuffer(source, accessor.count, stride, mode);
        if (encoded.length < source.length) {
          payload = Buffer.from(encoded);
          view.buffer = 1;
          view.extensions = { ...view.extensions, [EXTENSION]: {
            buffer: 0, byteOffset, byteLength: payload.length, byteStride: stride, count: accessor.count, mode,
          } };
          compressedViews++;
        }
      }
    }
    if (!view.extensions?.EXT_meshopt_compression) {
      view.buffer = 0;
      view.byteOffset = byteOffset;
    }
    const padding = Buffer.alloc((4 - payload.length % 4) % 4);
    payloads.push(payload, padding);
    byteOffset += payload.length + padding.length;
  });
  if (!compressedViews) return file;
  document.buffers = [
    { ...document.buffers[0], byteLength: byteOffset },
    // Required extension + placeholder buffer avoids shipping the uncompressed geometry too.
    { byteLength: original.document.buffers[0].byteLength, extensions: { [EXTENSION]: { fallback: true } } },
  ];
  document.extensionsUsed = [...(document.extensionsUsed ?? []), EXTENSION];
  document.extensionsRequired = [...(document.extensionsRequired ?? []), EXTENSION];
  const compressed = writeGlb(document, Buffer.concat(payloads));
  const decoded = await decodeBufferViews(readGlb(compressed));
  for (let i = 0; i < originalViews.length; i++) {
    assert.ok(originalViews[i].equals(decoded[i]), `Lossless verification failed for buffer view ${i}`);
  }
  return compressed.length < file.length ? compressed : file;
}

async function main() {
  const path = fileURLToPath(new URL("../public/models/endurace.glb", import.meta.url));
  const partsPath = new URL("../src/lib/parts.ts", import.meta.url);
  const original = await readFile(path);
  const compressed = await compressGlb(original);
  const version = createHash("sha256").update(compressed).digest("hex").slice(0, 12);
  const source = await readFile(partsPath, "utf8");
  const pattern = /export const MODEL_URL = "[^"]*";/g;
  assert.equal([...source.matchAll(pattern)].length, 1, "Expected exactly one MODEL_URL declaration");
  const updated = source.replace(pattern, `export const MODEL_URL = "/models/endurace.glb?v=${version}";`);
  if (!original.equals(compressed)) {
    await writeFile(`${path}.tmp`, compressed);
    await rename(`${path}.tmp`, path);
  }
  if (updated !== source) await writeFile(partsPath, updated);
  console.log(`[viewer] Lossless model: ${(original.length / 1e6).toFixed(1)} MB → ${(compressed.length / 1e6).toFixed(1)} MB; cache key ${version}`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error: unknown) => { console.error(error); process.exitCode = 1; });
}
