import { asset } from "./base-path.ts";
import { FREEHUB_AUDIO_URL } from "./freehub-recording.ts";
import { COAST_DAMPING, rpmToRadians } from "./wheel-physics.ts";

/** User-gesture activated recording at its original pitch, with speed-sensitive volume. */
export class FreehubAudio {
  private context: AudioContext | null = null;
  private gain: GainNode | null = null;
  private buffer: AudioBuffer | null = null;
  private source: AudioBufferSourceNode | null = null;
  private generation = 0;
  private active = false;
  private lastSpeed = 0;
  private lastObservedSpeed = 0;
  private completedCoast = false;
  readonly path: string;
  maxVolume = 1;

  constructor(path = asset(FREEHUB_AUDIO_URL)) {
    this.path = path;
  }

  /** Call directly inside a click/tap handler, before awaiting anything else. */
  async enable() {
    const generation = ++this.generation;
    const AudioContextClass = window.AudioContext ??
      (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) throw new Error("This browser does not support audio playback.");
    this.context ??= new AudioContextClass();
    const context = this.context;
    // resume() is invoked synchronously while the user activation is still valid.
    const resume = context.resume();
    const load = this.buffer ? Promise.resolve(this.buffer) : fetch(this.path, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error("Freehub sound could not be loaded.");
        return response.arrayBuffer();
      })
      .then((bytes) => context.decodeAudioData(bytes));
    const [, buffer] = await Promise.all([resume, load]);
    if (generation !== this.generation || context.state === "closed") return false;
    this.buffer = buffer;
    this.active = true;
    return true;
  }

  disable() {
    ++this.generation;
    this.active = false;
    this.fadeOut();
  }

  update(rearAngularVelocity: number, coasting = true) {
    if (!this.context || !this.buffer) return;
    const speed = Math.abs(rearAngularVelocity);
    if (speed < 0.16) {
      this.fadeOut();
      this.lastObservedSpeed = 0;
      this.completedCoast = false;
      return;
    }
    // A new spin/flick can restart the take; falling RPM must never restart it.
    if (speed > this.lastObservedSpeed + 0.01) {
      this.fadeOut();
      this.completedCoast = false;
    }
    this.lastObservedSpeed = speed;
    if (!this.active || !coasting || document.hidden) { this.fadeOut(); return; }
    if (this.context.state !== "running") return;
    const referenceOmega = rpmToRadians(180);
    if (!this.source) {
      if (this.completedCoast) return;
      // Resume in the slower part of the recording when sound is enabled mid-coast.
      const offset = Math.max(0, Math.log(referenceOmega / speed) / COAST_DAMPING);
      if (offset >= this.buffer.duration) { this.completedCoast = true; return; }
      const gain = this.context.createGain();
      gain.gain.value = 0;
      gain.connect(this.context.destination);
      const source = this.context.createBufferSource();
      source.buffer = this.buffer;
      source.loop = false;
      source.connect(gain);
      source.onended = () => {
        source.disconnect();
        gain.disconnect();
        if (this.source === source) {
          this.source = null;
          this.gain = null;
          this.lastSpeed = 0;
          this.completedCoast = true;
        }
      };
      this.gain = gain;
      this.source = source;
      source.start(0, offset);
    }
    const time = this.context.currentTime;
    // Resampling a mechanical recording changes the pitch of every click and its resonance.
    // Keep native playback speed; wheel velocity controls loudness and the stop fade.
    const volume = this.maxVolume * Math.min(1, speed / referenceOmega);
    this.gain!.gain.setTargetAtTime(volume, time, 0.07);
    this.lastSpeed = speed;
  }

  /** Silence background tabs immediately, even when requestAnimationFrame is paused. */
  pause() { this.fadeOut(); }

  get isPlaying() { return this.source !== null; }

  get status() {
    return { enabled: this.active, playing: this.isPlaying, speed: this.lastSpeed,
      contextState: this.context?.state ?? "uninitialized" };
  }

  private fadeOut() {
    if (!this.context || !this.gain || !this.source) return;
    const time = this.context.currentTime;
    this.gain.gain.setTargetAtTime(0, time, 0.035);
    const ending = this.source;
    ending.stop(time + 0.18);
    this.source = null;
    this.gain = null;
    this.lastSpeed = 0;
  }

  dispose() {
    this.disable();
    void this.context?.close().catch(() => {});
    this.context = null;
    this.gain = null;
    this.buffer = null;
    this.completedCoast = false;
    this.lastObservedSpeed = 0;
  }
}
