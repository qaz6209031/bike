import test, { type TestContext } from "node:test";
import assert from "node:assert/strict";
import { FreehubAudio } from "../src/lib/freehub-audio.ts";
import { FREEHUB_AUDIO_URL } from "../src/lib/freehub-recording.ts";
import { asset } from "../src/lib/base-path.ts";
import { rpmToRadians, WheelDrive } from "../src/lib/wheel-physics.ts";

function browserAudio(t: TestContext) {
  const calls: string[] = [];
  const sources: { stopped: boolean; rate: number; gainIndex: number; offset: number; finish: () => void; loop: boolean }[] = [];
  const gains: { values: number[]; disconnected: boolean }[] = [];
  const volumes: number[] = [];
  const requests: { url: string; cache: RequestCache | undefined }[] = [];
  const visibility = { hidden: false };
  class Context {
    state = "suspended";
    currentTime = 10;
    destination = {};
    constructor() { calls.push("context"); }
    resume() { calls.push("resume"); this.state = "running"; return Promise.resolve(); }
    decodeAudioData() { calls.push("decode"); return Promise.resolve({ duration: 41.924 } as AudioBuffer); }
    close() { this.state = "closed"; return Promise.resolve(); }
    createGain() {
      const id = gains.length;
      const state = { values: [] as number[], disconnected: false };
      gains.push(state);
      return { id, gain: { value: 0, setTargetAtTime(value: number) { volumes.push(value); state.values.push(value); } }, connect() {}, disconnect() { state.disconnected = true; } };
    }
    createBufferSource() {
      const source = { stopped: false, rate: 1, gainIndex: -1, offset: 0, finish: () => { created.onended?.(); }, loop: false };
      sources.push(source);
      const created = { buffer: null, loop: false, connect(gain: { id: number }) { source.gainIndex = gain.id; }, start(_when?: number, offset = 0) { calls.push("start"); source.offset = offset; source.loop = created.loop; }, disconnect() {},
        stop() { source.stopped = true; }, onended: null as (() => void) | null,
        playbackRate: { setTargetAtTime(rate: number) { source.rate = rate; } } };
      return created;
    }
  }
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, "document");
  const previousFetch = globalThis.fetch;
  Object.defineProperty(globalThis, "window", { value: { AudioContext: Context }, configurable: true });
  Object.defineProperty(globalThis, "document", { value: visibility, configurable: true });
  globalThis.fetch = async (input, init) => { calls.push("fetch"); requests.push({ url: String(input), cache: init?.cache }); return new Response(new Uint8Array(8)); };
  t.after(() => {
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow); else Reflect.deleteProperty(globalThis, "window");
    if (previousDocument) Object.defineProperty(globalThis, "document", previousDocument); else Reflect.deleteProperty(globalThis, "document");
    globalThis.fetch = previousFetch;
  });
  return { calls, sources, gains, volumes, visibility, requests };
}

test("audio is inert until enabled and resumes before waiting for the audio file", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  audio.update(20);
  assert.deepEqual(browser.calls, []);
  const enabling = audio.enable();
  assert.deepEqual(browser.calls.slice(0, 3), ["context", "resume", "fetch"]);
  assert.equal(await enabling, true);
  assert.equal(browser.sources.length, 0, "enabling sound while stationary does not play it");
  assert.deepEqual(browser.requests, [{ url: asset(FREEHUB_AUDIO_URL), cache: "no-store" }], "the replacement recording bypasses old browser audio caches");
});

test("freehub audio follows rear-wheel coast speed and fades to a stop", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  audio.update(0);
  assert.equal(browser.sources.length, 0);
  audio.update(10, false);
  assert.equal(browser.sources.length, 0, "a driven wheel must not play coasting sound");
  audio.update(20);
  const highVolume = browser.volumes.at(-1)!;
  audio.update(10);
  assert.ok(browser.volumes.at(-1)! < highVolume);
  assert.equal(browser.sources.length, 1, "the take continues while wheel speed decreases");
  audio.update(0.1);
  assert.equal(browser.volumes.at(-1), 0);
  assert.equal(browser.sources[0].stopped, true);
  assert.equal(audio.isPlaying, false);
});

test("mute and background-tab visibility silence the loop", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  audio.update(20);
  browser.visibility.hidden = true;
  audio.pause();
  assert.equal(audio.isPlaying, false);
  audio.update(20);
  assert.equal(browser.sources.length, 1, "hidden tabs never restart audio");
  browser.visibility.hidden = false;
  audio.update(20);
  assert.equal(browser.sources.length, 2);
  audio.disable();
  audio.update(20);
  assert.equal(browser.sources.length, 2, "muted audio stays stopped");
});

test("missing audio rejects cleanly so the UI can offer retry", async (t) => {
  browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  globalThis.fetch = async () => new Response(null, { status: 404 });
  await assert.rejects(audio.enable(), /could not be loaded/);
  assert.equal(audio.status.enabled, false);
});

test("rapid braking and spinning use separate gains so the fading loop stays silent", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  audio.update(20);
  audio.pause();
  assert.equal(browser.gains[0].values.at(-1), 0);
  audio.update(20);
  assert.equal(browser.sources.length, 2);
  assert.notEqual(browser.sources[0].gainIndex, browser.sources[1].gainIndex);
  assert.equal(browser.gains[0].values.at(-1), 0, "the old loop's fade is not raised by the new loop");
  browser.sources[0].finish();
  assert.equal(browser.gains[0].disconnected, true);
  assert.equal(browser.gains[1].disconnected, false);
  assert.equal(audio.isPlaying, true);
});

test("cancelling audio activation during loading leaves it disabled", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  let resolveFetch!: (response: Response) => void;
  globalThis.fetch = () => new Promise<Response>((resolve) => { resolveFetch = resolve; });
  const enabling = audio.enable();
  audio.disable();
  resolveFetch(new Response(new Uint8Array(8)));
  assert.equal(await enabling, false);
  audio.update(20);
  assert.equal(browser.sources.length, 0);
});

test("background friction lowers recording volume without changing pitch, then silences it at rest", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  const drive = new WheelDrive();
  t.after(() => audio.dispose());
  await audio.enable();
  drive.setVelocity("RearWheel", rpmToRadians(180));
  audio.update(drive.velocities.RearWheel);
  const initialVolume = browser.volumes.at(-1)!;
  const initialRate = browser.sources[0].rate;
  drive.step(3);
  audio.update(drive.velocities.RearWheel);
  assert.ok(browser.volumes.at(-1)! < initialVolume);
  assert.equal(browser.sources[0].rate, initialRate);
  assert.equal(initialRate, 1);
  drive.step(60);
  audio.update(drive.velocities.RearWheel);
  assert.equal(audio.isPlaying, false);
  assert.equal(browser.volumes.at(-1), 0);
});

test("the actual freehub recording keeps its native pitch across the full wheel-speed range", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  for (const rpm of [30, 180, 360, 60, -180]) {
    audio.update(rpmToRadians(rpm));
    assert.equal(browser.sources.at(-1)!.rate, 1, `native pitch at ${rpm} RPM`);
  }
});

test("falling RPM never wraps or restarts the louder beginning of the recording", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  audio.update(rpmToRadians(180));
  assert.equal(browser.sources[0].loop, false);
  for (const rpm of [160, 120, 60, 30]) audio.update(rpmToRadians(rpm));
  assert.equal(browser.sources.length, 1);
  browser.sources[0].finish();
  for (const rpm of [20, 10, 5]) audio.update(rpmToRadians(rpm));
  assert.equal(browser.sources.length, 1, "the end of the take remains silent during the same coast");
  audio.update(rpmToRadians(180));
  assert.equal(browser.sources.length, 2, "a new spin can start a new coasting take");
});

test("enabling sound at low RPM starts in the slower part of the recording", async (t) => {
  const browser = browserAudio(t);
  const audio = new FreehubAudio();
  t.after(() => audio.dispose());
  await audio.enable();
  audio.update(rpmToRadians(30));
  assert.ok(browser.sources[0].offset > 10);
  assert.equal(browser.sources[0].rate, 1);
  assert.equal(browser.sources[0].loop, false);
});
