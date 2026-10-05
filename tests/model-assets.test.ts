import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { FREEHUB_AUDIO_URL } from "../src/lib/freehub-recording.ts";
import { Box3, Matrix4, Quaternion, Vector3 } from "three";

type Node = { name: string; mesh?: number; children?: number[]; translation?: number[]; rotation?: number[]; scale?: number[]; matrix?: number[]; extras?: { frameSize?: string; pivotAtAxle?: boolean; wheelAxis?: number[] } };
type Accessor = { bufferView: number; byteOffset?: number; count: number; componentType: number; type: string };
type GLTF = {
  nodes: Node[];
  meshes: { primitives: { attributes: { POSITION: number }; indices: number }[] }[];
  accessors: Accessor[];
  bufferViews: { byteOffset?: number; byteStride?: number }[];
  buffers: { uri?: string; byteLength: number }[];
  images: { uri?: string; bufferView?: number }[];
  extensionsUsed: string[];
};

const file = readFileSync(new URL("../public/models/endurace.glb", import.meta.url));
const jsonLength = file.readUInt32LE(12);
const gltf: GLTF = JSON.parse(file.subarray(20, 20 + jsonLength).toString());
const binaryStart = 20 + jsonLength + 8;
const index = (name: string) => gltf.nodes.findIndex((node) => node.name === name);
const node = (name: string) => {
  const i = index(name);
  assert.ok(i >= 0, `${name} must be present`);
  return gltf.nodes[i];
};

function descendants(i: number): number[] {
  return (gltf.nodes[i].children ?? []).flatMap((child) => [child, ...descendants(child)]);
}

function matrix(n: Node) {
  if (n.matrix) return new Matrix4().fromArray(n.matrix);
  return new Matrix4().compose(
    new Vector3().fromArray(n.translation ?? [0, 0, 0]),
    new Quaternion().fromArray(n.rotation ?? [0, 0, 0, 1]),
    new Vector3().fromArray(n.scale ?? [1, 1, 1]),
  );
}

function worldMatrix(i: number): Matrix4 {
  const parent = gltf.nodes.findIndex((n) => n.children?.includes(i));
  return parent < 0 ? matrix(gltf.nodes[i]) : worldMatrix(parent).multiply(matrix(gltf.nodes[i]));
}

function tireBounds(wheel: string, angle: number) {
  const wi = index(wheel);
  const ti = descendants(wi).find((i) => gltf.nodes[i].name.endsWith("_tire"));
  assert.notEqual(ti, undefined);
  const t = gltf.nodes[ti!];
  const parent = gltf.nodes.findIndex((n) => n.children?.includes(ti!));
  assert.equal(parent, wi, "tire is a direct child of the axle pivot");
  const rotation = new Matrix4().makeRotationAxis(new Vector3().fromArray(node(wheel).extras!.wheelAxis!), angle);
  const transform = worldMatrix(wi).multiply(rotation).multiply(matrix(t));
  const bounds = new Box3();
  for (const primitive of gltf.meshes[t.mesh!].primitives) {
    const accessor = gltf.accessors[primitive.attributes.POSITION];
    assert.equal(accessor.componentType, 5126, "positions are float32");
    const view = gltf.bufferViews[accessor.bufferView];
    const offset = binaryStart + (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
    const stride = view.byteStride ?? 12;
    for (let i = 0; i < accessor.count; i++) {
      const p = offset + i * stride;
      bounds.expandByPoint(new Vector3(file.readFloatLE(p), file.readFloatLE(p + 4), file.readFloatLE(p + 8)).applyMatrix4(transform));
    }
  }
  return bounds;
}

test("the exported bike is complete, self-contained, and has named component groups", () => {
  assert.equal(file.readUInt32LE(0), 0x46546c67);
  assert.equal(file.readUInt32LE(4), 2);
  assert.equal(file.readUInt32LE(8), file.length);
  for (const name of ["Frame", "FrontWheel", "RearWheel", "FrontHub", "RearHub", "Crank", "Pedals", "RearLight", "FrontDerailleur", "RearDerailleur"]) node(name);
  const manifest = JSON.parse(readFileSync(new URL("../public/models/manifest.json", import.meta.url), "utf8"));
  assert.equal(gltf.meshes.length, manifest.meshObjects, "all mesh and curve objects in the exported model are present");
  assert.equal(node("Endurace_CF_SLX_7_AXS_S").extras?.frameSize, "S");
  const frontAxle = new Vector3().setFromMatrixPosition(worldMatrix(index("FrontWheel")));
  const rearAxle = new Vector3().setFromMatrixPosition(worldMatrix(index("RearWheel")));
  assert.ok(Math.abs(frontAxle.x - rearAxle.x - 1.008) < 1e-6, "the exported size S wheelbase is 1008 mm");
  assert.ok(gltf.buffers.every((buffer) => !buffer.uri));
  assert.ok(gltf.images.every((image) => !image.uri && image.bufferView !== undefined));
  assert.ok(gltf.extensionsUsed.includes("KHR_materials_clearcoat"));
  assert.ok(gltf.extensionsUsed.includes("KHR_materials_anisotropy"));
});

for (const wheel of ["FrontWheel", "RearWheel"]) {
  test(`${wheel} rotates around its tyre centre and actual axle`, () => {
    const w = node(wheel);
    assert.equal(w.extras?.pivotAtAxle, true);
    const before = tireBounds(wheel, 0);
    const after = tireBounds(wheel, Math.PI / 2);
    const center = new Vector3().setFromMatrixPosition(worldMatrix(index(wheel)));
    assert.ok(before.getCenter(new Vector3()).distanceTo(center) < 1e-6);
    assert.ok(after.getCenter(new Vector3()).distanceTo(center) < 1e-6);
    assert.ok(before.getSize(new Vector3()).distanceTo(after.getSize(new Vector3())) < 1e-6);
    const size = before.getSize(new Vector3());
    assert.ok(Math.abs(size.x - 0.686) < 1e-4);
    assert.ok(Math.abs(size.y - 0.686) < 1e-4);
    assert.ok(size.z < 0.033, "axle is perpendicular to the wheel plane");
  });
}

test("hubs turn with the wheels; cassette, through axles and brakes stay stationary", () => {
  const front = descendants(index("FrontWheel")).map((i) => gltf.nodes[i].name);
  const rear = descendants(index("RearWheel")).map((i) => gltf.nodes[i].name);
  assert.ok(front.includes("FrontHub"));
  assert.ok(rear.includes("RearHub"));
  assert.ok(![...front, ...rear].some((name) => /_axle|cassette|^cog_|caliper|^chain$/.test(name)));
  assert.equal(descendants(index("Drivetrain")).filter((i) => gltf.nodes[i].name.startsWith("cog_")).length, 12);
});

test("the freehub audio uses the owner's complete, native coasting take without looping", () => {
  const wav = readFileSync(new URL("../public/audio/freehub.wav", import.meta.url));
  assert.equal(wav.toString("ascii", 0, 4), "RIFF");
  assert.equal(wav.toString("ascii", 8, 12), "WAVE");
  assert.equal(wav.readUInt32LE(24), 48000);
  assert.equal(wav.readUInt16LE(22), 2);
  assert.equal(wav.readUInt16LE(34), 16);
  const metadata = JSON.parse(readFileSync(new URL("../public/audio/freehub.json", import.meta.url), "utf8"));
  assert.equal(metadata.kind, "owner-recording");
  assert.equal(metadata.source, "sound.MOV");
  assert.match(metadata.sourceSha256, /^[0-9a-f]{64}$/);
  const bytesPerFrame = metadata.channels * 2;
  assert.equal((wav.length - 44) / bytesPerFrame / metadata.sampleRate, metadata.audioSeconds);
  assert.ok(metadata.audioSeconds > 40, "the full coast replaces the repeating short excerpt");
  assert.equal(createHash("sha256").update(wav).digest("hex"), metadata.audioSha256);
  assert.equal(FREEHUB_AUDIO_URL, `/audio/freehub.wav?v=${metadata.audioSha256.slice(0, 12)}`);
  assert.equal(metadata.playbackRate, 1);
  assert.equal(metadata.playbackMode, "single-coast");
  assert.deepEqual(metadata.processing, { equalization: false, normalization: false, channelMixing: false, resampling: false });
  assert.ok(wav.subarray(44).some((byte) => byte > 0));
  let peak = 0;
  for (let i = 44 + bytesPerFrame; i < wav.length; i += 2) {
    const sample = wav.readInt16LE(i);
    peak = Math.max(peak, Math.abs(sample));
  }
  assert.ok(peak < 32767, "the recording is not clipped");
});
