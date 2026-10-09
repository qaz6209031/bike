import test from "node:test";
import assert from "node:assert/strict";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { compressGlb, readGlb, writeGlb, type GlbDocument } from "../scripts/compress-model.ts";

test("lossless compression preserves float bits, index order, textures, and scene metadata", async () => {
  const positions = Buffer.alloc(128 * 12);
  // Include negative zero, a subnormal, and adjacent floats that quantization would change.
  const bits = [0, 0x80000000, 0x00000001, 0x3f800000, 0x3f800001, 0xbf800000];
  for (let i = 0; i < positions.length / 4; i++) positions.writeUInt32LE(bits[i % bits.length], i * 4);
  const indices = Buffer.alloc(384 * 4);
  const triangles = [0, 2, 1, 2, 3, 1];
  for (let i = 0; i < indices.length / 4; i++) indices.writeUInt32LE(triangles[i % triangles.length], i * 4);
  const texture = Buffer.from("original embedded texture bytes");
  const binary = Buffer.concat([positions, indices, texture]);
  const document: GlbDocument = {
    asset: { version: "2.0" },
    nodes: [{ name: "RearWheel", mesh: 0, extras: { pivotAtAxle: true, wheelAxis: [0, 0, 1] } }],
    meshes: [{ primitives: [{ attributes: { POSITION: 0 }, indices: 1 }] }],
    materials: [{ name: "Crystal White", extensions: { KHR_materials_clearcoat: { clearcoatFactor: 1 } } }],
    images: [{ bufferView: 2, mimeType: "image/png" }],
    buffers: [{ byteLength: binary.length }],
    bufferViews: [
      { buffer: 0, byteOffset: 0, byteLength: positions.length },
      { buffer: 0, byteOffset: positions.length, byteLength: indices.length },
      { buffer: 0, byteOffset: positions.length + indices.length, byteLength: texture.length },
    ],
    accessors: [
      { bufferView: 0, count: 128, componentType: 5126, type: "VEC3" },
      { bufferView: 1, count: 384, componentType: 5125, type: "SCALAR" },
    ],
    extensionsUsed: ["KHR_materials_clearcoat"],
  };
  const original = writeGlb(document, binary);
  const compressed = await compressGlb(original);
  assert.ok(compressed.length < original.length);
  const result = readGlb(compressed);
  for (const key of ["nodes", "meshes", "materials", "images", "accessors"]) {
    assert.deepEqual(result.document[key], document[key], `${key} must remain unchanged`);
  }
  assert.ok(result.document.extensionsRequired?.includes("EXT_meshopt_compression"));
  await MeshoptDecoder.ready;
  // Decode with Three's runtime decoder, independently of the compressor's verification helper.
  for (const [index, expected] of [positions, indices, texture].entries()) {
    const view = result.document.bufferViews[index];
    const extension = view.extensions?.EXT_meshopt_compression;
    if (extension) {
      assert.ok(!extension.filter, "Lossy filters must not be used");
      const decoded = Buffer.alloc(view.byteLength);
      const start = extension.byteOffset ?? 0;
      MeshoptDecoder.decodeGltfBuffer(decoded, extension.count, extension.byteStride,
        result.binary.subarray(start, start + extension.byteLength), extension.mode);
      assert.deepEqual(decoded, expected);
    } else {
      const start = view.byteOffset ?? 0;
      assert.deepEqual(result.binary.subarray(start, start + view.byteLength), expected);
    }
  }
  assert.deepEqual(await compressGlb(compressed), compressed, "Re-running compression must leave the asset unchanged");
});
