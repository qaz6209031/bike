"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Component, useCallback, useEffect, useRef, useState, type ErrorInfo, type ReactNode } from "react";
import { FreehubAudio } from "@/lib/freehub-audio";
import { WheelDrive, rpmToRadians, type WheelTarget } from "@/lib/wheel-physics";
import { asset } from "@/lib/base-path";
import { BIKE_SIZE, COMPONENT_SOURCE, ENVIRONMENT_URL, MODEL_URL, UPGRADE_PARTS, type CameraView, type PartName } from "@/lib/parts";
import { setTheme, useTheme } from "@/lib/theme";
import type { CameraCommand, ModelInfo } from "./bike-scene";
import Icon from "./icons";
import ModelLoading from "./model-loading";

const BikeScene = dynamic(() => import("./bike-scene"), { ssr: false });

class ViewerBoundary extends Component<{ children: ReactNode; onRetry: () => void; onFailure: () => void }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("3D viewer failed:", error.message, info.componentStack);
    this.props.onFailure();
  }
  render() {
    return this.state.error ? <div className="viewer-notice viewer-error" role="alert"><Icon name="info" size={28} /><h2>The model couldn’t load.</h2><p>Check your connection, then try again.</p><button className="button button-primary" onClick={this.props.onRetry}>Reload model <Icon name="reset" /></button></div> : this.props.children;
  }
}

const initialInfo: ModelInfo = { parts: [], meshes: 0, dimensions: [0, 0, 0], frameSize: null };
const PHONE_SPIN_RPM = 180;
const PHONE_FRAMING = 0.82;              // the box fit is loose at 3/4 view; fill the landscape screen

/** Phones (touch screen, shorter side <= 600 px) get a landscape-only, model-first layout. */
function usePhoneMode() {
  const [mode, setMode] = useState<{ phone: boolean; portrait: boolean } | null>(null);
  useEffect(() => {
    const coarse = window.matchMedia("(pointer: coarse)");
    const portrait = window.matchMedia("(orientation: portrait)");
    const update = () => setMode({
      phone: new URLSearchParams(window.location.search).has("phone")          // ?phone forces it (testing)
        || (coarse.matches && Math.min(window.screen.width, window.screen.height) <= 600),
      portrait: portrait.matches,
    });
    update();
    coarse.addEventListener("change", update);
    portrait.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => {
      coarse.removeEventListener("change", update);
      portrait.removeEventListener("change", update);
      window.removeEventListener("resize", update);
    };
  }, []);
  return mode;
}

/** On browsers that allow it (Android Chrome), go fullscreen and lock to landscape. iOS ignores this. */
function enterLandscapeFullscreen() {
  const root = document.documentElement;
  if (!document.fullscreenEnabled || document.fullscreenElement || !root.requestFullscreen) return;
  root.requestFullscreen({ navigationUI: "hide" })
    .then(() => (screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> }).lock?.("landscape"))
    .catch(() => undefined);
}

export default function ViewerShell() {
  const [drive] = useState(() => new WheelDrive());
  const [audio] = useState(() => new FreehubAudio());
  const theme = useTheme();
  const [view, setView] = useState<CameraView>("perspective");
  const [selected, setSelected] = useState<PartName | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfo>(initialInfo);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");
  const [rpm, setRpm] = useState(180);
  const [target, setTarget] = useState<WheelTarget>("RearWheel");
  const [stats, setStats] = useState({ front: 0, rear: 0, sound: false });
  const [sound, setSound] = useState<"off" | "loading" | "on" | "error">("off");
  const [audioError, setAudioError] = useState("");
  const [retry, setRetry] = useState(0);
  const [cameraCommand, setCameraCommand] = useState<CameraCommand>({ kind: "reset", sequence: 0 });
  const [help, setHelp] = useState(false);
  const mounted = useRef(false);
  const triedFullscreen = useRef(false);
  const mode = usePhoneMode();

  useEffect(() => {
    mounted.current = true;
    const hideAudio = () => { if (document.hidden) audio.pause(); };
    document.addEventListener("visibilitychange", hideAudio);
    return () => {
      mounted.current = false;
      document.removeEventListener("visibilitychange", hideAudio);
      audio.dispose();
      drive.stop();
    };
  }, [audio, drive]);

  const onReady = useCallback((info: ModelInfo) => { setModelInfo(info); setLoadState("ready"); }, []);
  const onFailure = useCallback(() => {
    drive.stop();
    audio.pause();
    setModelInfo(initialInfo);
    setStats({ front: 0, rear: 0, sound: false });
    setSelected(null);
    setLoadState("error");
  }, [audio, drive]);
  const onStats = useCallback((next: typeof stats) => setStats(next), []);
  const select = useCallback((part: PartName | null) => setSelected(part), []);
  const ready = loadState === "ready" && modelInfo.meshes > 0;
  const selectedPart = UPGRADE_PARTS.find((part) => part.name === selected);
  const available = UPGRADE_PARTS.filter((part) => modelInfo.parts.includes(part.name));
  const speed = target === "both" ? Math.max(stats.front, stats.rear) : target === "FrontWheel" ? stats.front : stats.rear;
  const moving = speed > 0;

  function cameraAction(kind: CameraCommand["kind"]) {
    setCameraCommand((previous) => ({ kind, sequence: previous.sequence + 1 }));
  }

  async function toggleSound() {
    if (sound === "on") { audio.disable(); setSound("off"); return; }
    await enableSound();
  }

  async function enableSound() {
    setSound("loading");
    setAudioError("");
    try {
      // enable() creates/resumes AudioContext immediately inside this click handler.
      const enabled = await audio.enable();
      if (mounted.current) setSound(enabled ? "on" : "off");
    } catch (error) {
      audio.disable();
      if (mounted.current) {
        setSound("error");
        setAudioError(error instanceof Error ? error.message : "Sound couldn’t be enabled. Tap to try again.");
      }
    }
  }

  /** Phone: the one button. Its tap is the user gesture that turns sound on (browsers need one). */
  function spinRearWheel() {
    if (sound !== "on" && sound !== "loading") void enableSound();   // audio.enable() runs synchronously here
    drive.setVelocity("RearWheel", rpmToRadians(PHONE_SPIN_RPM));
    if (!triedFullscreen.current) { triedFullscreen.current = true; enterLandscapeFullscreen(); }
  }

  async function reloadModel() {
    drive.stop();
    audio.pause();
    const { useGLTF, useEnvironment } = await import("@react-three/drei");
    useGLTF.clear(asset(MODEL_URL));
    useEnvironment.clear({ files: asset(ENVIRONMENT_URL) });
    setModelInfo(initialInfo);
    setLoadState("loading");
    setRetry((previous) => previous + 1);
  }

  if (mode === null) return <div className="phone-pending" />;

  if (mode.phone) {
    const canSpin = ready && modelInfo.parts.includes("RearWheel");
    return <div className="phone-shell">
      <div className="phone-canvas" aria-label="Interactive 3D bicycle viewer">
        <ViewerBoundary key={retry} onRetry={reloadModel} onFailure={onFailure}>
          <BikeScene theme={theme} view="perspective" framing={PHONE_FRAMING} selected={null} drive={drive} audio={audio} cameraCommand={cameraCommand} onSelect={() => undefined} onReady={onReady} onStats={onStats} dimensions={modelInfo.dimensions} />
          {loadState === "loading" ? <ModelLoading /> : null}
        </ViewerBoundary>
      </div>
      <button className={`phone-spin ${stats.rear > 0 ? "spinning" : ""}`} disabled={!canSpin} onClick={spinRearWheel}>
        <Icon name="wheel" size={22} />Spin rear wheel
      </button>
      {mode.portrait ? <div className="rotate-notice" role="alert">
        <span className="rotate-glyph"><Icon name="rotate" size={56} /></span>
        <strong>Rotate your phone</strong><p>The bike viewer works in landscape.</p>
      </div> : null}
    </div>;
  }

  return <div className="studio-shell">
    <header className="site-header">
      <Link href="/" className="wordmark" aria-label="Kai’s Bike home"><span className="brand-symbol"><i /><i /><i /></span><span>KAI’S<span className="wordmark-sub">BIKE</span></span></Link>
      <div className="header-caption"><span className="status-dot" /> A closer look at your ride</div>
      <div className="header-actions"><button className="theme-toggle" aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"} aria-pressed={theme === "dark"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}><Icon name={theme === "dark" ? "sun" : "moon"} /><span>{theme === "dark" ? "Light mode" : "Dark mode"}</span></button></div>
    </header>

    <main className="studio-main">
      <section className="viewer-stage" aria-label="Interactive 3D bicycle viewer">
        <div className="model-heading"><p className="eyebrow">CANYON / PERSONAL BUILD</p><h1>Endurace<span className="title-dot">.</span></h1><p className="model-subtitle">CF SLX 7 AXS · Size {BIKE_SIZE}</p><span className="paint-chip"><i />Crystal White</span></div>
        <div className="canvas-container" data-testid="viewer-canvas">
          <ViewerBoundary key={retry} onRetry={reloadModel} onFailure={onFailure}>
            <BikeScene theme={theme} view={view} selected={selectedPart?.name ?? null} drive={drive} audio={audio} cameraCommand={cameraCommand} onSelect={select} onReady={onReady} onStats={onStats} dimensions={modelInfo.dimensions} />
            {loadState === "loading" ? <ModelLoading /> : null}
          </ViewerBoundary>
        </div>
        {selectedPart ? <div className="selected-label"><span className="status-dot orange" /><span><strong>{selectedPart.label}</strong><small>{selectedPart.detail}</small></span><button className="clear-selection" onClick={() => select(null)} aria-label="Clear selected upgrade">×</button></div> : null}
        <div className="camera-presets" role="group" aria-label="Camera angle">
          {(["perspective", "side", "front"] as const).map((preset) => <button key={preset} className={view === preset ? "active" : ""} aria-pressed={view === preset} onClick={() => setView(preset)}>{preset === "perspective" ? "3/4 view" : `${preset[0].toUpperCase()}${preset.slice(1)}`}</button>)}
        </div>
        <div className="stage-bottom">
          <button className="interaction-hint" aria-expanded={help} aria-controls="viewer-help" onClick={() => setHelp((previous) => !previous)}><Icon name="orbit" /><span><span className="desktop-hint">Drag to explore<span className="desktop-only"> · Scroll to zoom</span></span><span className="mobile-only">Drag · Pinch to zoom</span></span><Icon name="info" size={14} /></button>
          <div className="camera-tools"><button aria-label="Zoom in" onClick={() => cameraAction("in")}><Icon name="plus" /></button><button aria-label="Zoom out" onClick={() => cameraAction("out")}><Icon name="minus" /></button><span /><button aria-label="Reset camera" onClick={() => cameraAction("reset")}><Icon name="reset" /></button></div>
        </div>
        <div id="viewer-help" className="interaction-help" hidden={!help}><strong>Take a look around</strong><p>Drag with one finger or the left mouse button to orbit. Pinch or scroll to zoom. Use two fingers or the right mouse button to pan. Tap an upgrade or accessory to select it.</p><button onClick={() => setHelp(false)}>Got it <Icon name="check" size={14} /></button></div>
        <div className="stage-watermark" aria-hidden="true">ENGINEERED TO EXPLORE</div>
      </section>

      <nav className="mobile-section-nav" aria-label="Viewer sections"><a href="#wheel-controls">Wheel controls <Icon name="chevron" size={16} /></a></nav>

      <aside className="controls-panel" aria-label="Model and wheel controls">
        <div className="panel-intro"><p className="eyebrow">YOUR PERSONAL BUILD</p><h2>Your upgrades.<br />Your ride.</h2><p>The additions that make it yours.</p></div>
        <section id="bike-upgrades" className="components-section"><div className="section-heading"><h3><span>01</span> Upgrades</h3><span className="count-pill" aria-label={`${available.length} available upgrades`}>{String(available.length).padStart(2, "0")}</span></div>
          <div className="parts-list" aria-label="Select an upgrade">
            {available.map((part) => <button className={`part-button ${selected === part.name ? "selected" : ""}`} key={part.name} onClick={() => select(selected === part.name ? null : part.name)} aria-pressed={selected === part.name}><span className="part-marker" /><span className="part-text"><strong>{part.label}</strong><small>{part.detail}</small></span><Icon name="chevron" size={14} /></button>)}
            {!ready ? <p className="parts-placeholder">{loadState === "error" ? "Model unavailable" : "Loading upgrades…"}</p> : null}
          </div>
          <p className="component-note">Or tap an upgrade directly on the model.</p>
          <a className="component-source" href={COMPONENT_SOURCE} target="_blank" rel="noopener noreferrer">Original bike specifications <Icon name="arrow" size={12} /></a>
        </section>

        <section id="wheel-controls" className="wheel-section"><div className="section-heading"><h3><span>02</span> Set it in motion</h3><Icon name="wheel" size={19} /></div>
          <div className="wheel-top-row"><label className="sr-only" htmlFor="wheel-target">Wheel to spin</label><select id="wheel-target" value={target} disabled={!ready} onChange={(event) => setTarget(event.target.value as WheelTarget)}><option value="RearWheel">Rear wheel</option><option value="FrontWheel">Front wheel</option><option value="both">Both wheels</option></select><span className={`coast-badge ${moving ? "moving" : ""}`}><i />{moving ? "Coasting" : "At rest"}</span></div>
          <div className="speed-readout"><strong data-testid="wheel-rpm">{Math.round(speed)}</strong><span>RPM<small>LIVE SPEED</small></span><div className={`wheel-indicator ${moving ? "spinning" : ""}`}><Icon name="wheel" size={41} /></div></div>
          <label className="range-label" htmlFor="launch-speed"><span>Spin speed</span><strong>{rpm} <small>rpm</small></strong></label><input id="launch-speed" type="range" min="30" max="360" step="10" value={rpm} onChange={(event) => setRpm(Number(event.target.value))} aria-valuetext={`${rpm} revolutions per minute`} />
          <p className="spin-note">Coasts to a stop. Press Brake to stop sooner.</p>
          <div className="wheel-actions"><button className="button button-primary" disabled={!ready || !(target === "both" ? ["FrontWheel", "RearWheel"].every((name) => modelInfo.parts.includes(name)) : modelInfo.parts.includes(target))} onClick={() => drive.setVelocity(target, rpmToRadians(rpm))}>Spin wheel<Icon name="arrow" /></button><button className="button button-secondary" disabled={!ready} onClick={() => { drive.stop(); audio.pause(); }}><Icon name="brake" size={16} />Brake</button></div>
          <div className="sound-row"><span><strong>Hear the freehub</strong><small>{stats.sound && sound === "on" ? "Coasting with sound" : "Sound follows rear-wheel speed"}</small></span><button className={`sound-toggle ${sound === "on" ? "enabled" : ""}`} aria-label={sound === "on" ? "Disable freehub sound" : "Enable freehub sound"} aria-pressed={sound === "on"} disabled={sound === "loading"} onClick={toggleSound}><Icon name={sound === "on" ? "sound" : "mute"} size={17} />{sound === "loading" ? "…" : sound === "on" ? "On" : "Off"}</button></div>
          {audioError ? <p className="audio-error" role="alert">{audioError}</p> : null}
        </section>
        <div className="panel-footnote"><span className="finish-swatch" /><span>White gloss. Carbon weave.<br />Made for a closer look.</span></div>
      </aside>
    </main>
    <footer className="site-footer"><span><span className="status-dot" />{loadState === "error" ? "Model unavailable" : ready ? "3D model ready" : "Preparing 3D model"}</span><span className="footer-center">CANYON ENDURACE / KAI’S BUILD</span><span>ORBIT. EXPLORE. RIDE.</span></footer>
  </div>;
}
