"use client";

import { memo, Suspense, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { AdaptiveDpr, ContactShadows, Environment, OrbitControls, useGLTF } from "@react-three/drei";
import { AdditiveBlending, DataTexture, LinearFilter, Mesh, MeshStandardMaterial, RGBAFormat, Vector3, type Object3D, type Color } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three/addons/controls/OrbitControls.js";
import { asset } from "@/lib/base-path";
import { ENVIRONMENT_URL, MODEL_URL, PARTS, UPGRADE_PARTS, partObjectNames, type CameraView, type PartName } from "@/lib/parts";
import type { Theme } from "@/lib/theme";
import { fittedCameraPosition, modelBounds, wheelPivot, type Dimensions } from "@/lib/model-transforms";
import { radiansToRpm, type WheelDrive } from "@/lib/wheel-physics";
import type { FreehubAudio } from "@/lib/freehub-audio";

export type ModelInfo = { parts: string[]; meshes: number; dimensions: [number, number, number]; frameSize: string | null };
export type CameraCommand = { kind: "reset" | "in" | "out"; sequence: number };
export type SceneProps = {
  url?: string;
  theme: Theme;
  view: CameraView;
  selected: PartName | null;
  drive: WheelDrive;
  audio: FreehubAudio;
  cameraCommand: CameraCommand;
  onSelect: (part: PartName | null) => void;
  /** Camera distance multiplier over the bounding-box fit (1.12 default; smaller = bike fills more). */
  framing?: number;
  onReady: (info: ModelInfo) => void;
  onStats: (stats: { front: number; rear: number; sound: boolean }) => void;
  dimensions?: Dimensions;
};

function highlightPart(object: Object3D, materials: Map<MeshStandardMaterial, { emissive: Color; intensity: number }>, selected: PartName | null, theme: Theme) {
  for (const [mat, original] of materials) {
    mat.emissive.copy(original.emissive);
    mat.emissiveIntensity = original.intensity;
  }
  const part = PARTS.find((part) => part.name === selected);
  for (const name of part ? partObjectNames(part) : []) {
    object.getObjectByName(name)?.traverse((child) => {
      if (!(child instanceof Mesh)) return;
      // Keep the glowing red lens lit when its housing is selected in dark mode.
      if (theme === "dark" && (child.name === "flash_lens" || child.name === "flash_led_bar")) return;
      for (const mat of Array.isArray(child.material) ? child.material : [child.material]) {
        if (mat instanceof MeshStandardMaterial) {
          mat.emissive.set("#eb653f");
          mat.emissiveIntensity = 0.18;
        }
      }
    });
  }
}

function RearLightGlow({ position }: { position: [number, number, number] }) {
  const texture = useMemo(() => {
    const width = 64, height = 128;
    const pixels = new Uint8Array(width * height * 4);
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      const radius = Math.hypot((x + 0.5) / width * 2 - 1, (y + 0.5) / height * 2 - 1);
      const offset = (y * width + x) * 4;
      pixels[offset] = pixels[offset + 1] = pixels[offset + 2] = 255;
      pixels[offset + 3] = Math.round(Math.max(0, 1 - radius) ** 2 * 255);
    }
    const map = new DataTexture(pixels, width, height, RGBAFormat);
    map.magFilter = map.minFilter = LinearFilter;
    map.needsUpdate = true;
    return map;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return <group position={position}>
    <sprite scale={[0.05, 0.105, 1]} raycast={() => {}}>
      <spriteMaterial map={texture} color="#ff3020" opacity={0.2} transparent blending={AdditiveBlending} depthWrite={false} toneMapped={false} />
    </sprite>
    <pointLight color="#ff3020" intensity={0.006} distance={0.25} decay={2} />
  </group>;
}

const Model = memo(function Model({ url = asset(MODEL_URL), theme, selected, drive, audio, onSelect, onReady, onStats }: SceneProps) {
  const { scene: cached } = useGLTF(url);
  const model = useMemo(() => {
    const object = cached.clone(true);
    const materials = new Map<MeshStandardMaterial, { emissive: Color; intensity: number }>();
    let meshes = 0;
    let frameSize: string | null = null;
    object.traverse((child) => {
      const namedSize = child.name.match(/^Endurace_CF_SLX_7_AXS_(2XS|XS|S|M|L|XL|2XL)$/)?.[1];
      if (namedSize) frameSize = child.userData.frameSize ?? namedSize;
      if (!(child instanceof Mesh)) return;
      meshes++;
      child.castShadow = true;
      child.receiveShadow = true;
      const cloneMaterial = (material: MeshStandardMaterial) => {
        const copy = material.clone();
        if (copy instanceof MeshStandardMaterial) materials.set(copy, { emissive: copy.emissive.clone(), intensity: copy.emissiveIntensity });
        return copy;
      };
      child.material = Array.isArray(child.material) ? child.material.map(cloneMaterial) : cloneMaterial(child.material);
    });
    if (!meshes) throw new Error("The model contains no visible mesh geometry.");
    const { dimensions, center, scale } = modelBounds(object);
    const wheels = { FrontWheel: wheelPivot(object, "FrontWheel"), RearWheel: wheelPivot(object, "RearWheel") };
    const axes = {
      FrontWheel: new Vector3(...(wheels.FrontWheel?.userData.wheelAxis ?? [0, 0, 1]) as [number, number, number]).normalize(),
      RearWheel: new Vector3(...(wheels.RearWheel?.userData.wheelAxis ?? [0, 0, 1]) as [number, number, number]).normalize(),
    };
    const parts = PARTS.filter((part) => partObjectNames(part).some((name) => object.getObjectByName(name))).map((part) => part.name);
    const lens = object.getObjectByName("flash_lens");
    // Place the glow just outside the rear-facing lens, in the model's own coordinates.
    const rearGlowPosition = lens ? object.worldToLocal(lens.getWorldPosition(new Vector3())
      .addScaledVector(new Vector3(-1, 0, 0).transformDirection(lens.matrixWorld), 0.004)).toArray() : null;
    return { object, center, scale, dimensions, wheels, axes, parts, meshes, materials, frameSize, rearGlowPosition };
  }, [cached]);

  useEffect(() => {
    onReady({ parts: model.parts, meshes: model.meshes, dimensions: model.dimensions.clone().multiplyScalar(model.scale).toArray(), frameSize: model.frameSize });
    return () => { for (const material of model.materials.keys()) material.dispose(); };
  }, [model, onReady]);

  useEffect(() => {
    highlightPart(model.object, model.materials, selected, theme);
  }, [selected, model, theme]);

  const lastStats = useRef(0);
  const skipFrame = useRef(false);
  useEffect(() => {
    const visibilityChanged = () => { skipFrame.current = true; };
    document.addEventListener("visibilitychange", visibilityChanged);
    return () => document.removeEventListener("visibilitychange", visibilityChanged);
  }, []);
  useFrame((state, elapsed) => {
    if (document.hidden) { skipFrame.current = true; return; }
    if (skipFrame.current) { skipFrame.current = false; return; }
    const travel = drive.step(elapsed);
    for (const name of ["FrontWheel", "RearWheel"] as const) {
      model.wheels[name]?.rotateOnAxis(model.axes[name], travel[name]);
    }
    audio.update(model.wheels.RearWheel ? drive.velocities.RearWheel : 0);
    if (state.clock.elapsedTime - lastStats.current > 0.12) {
      lastStats.current = state.clock.elapsedTime;
      onStats({ front: Math.abs(radiansToRpm(drive.velocities.FrontWheel)), rear: Math.abs(radiansToRpm(drive.velocities.RearWheel)), sound: audio.isPlaying });
    }
  });

  function select(event: ThreeEvent<MouseEvent>) {
    if (event.delta > 4) return; // A drag rotates the view; a click selects a component.
    event.stopPropagation();
    let node: Object3D | null = event.object;
    while (node) {
      const part = UPGRADE_PARTS.find((part) => partObjectNames(part).includes(node?.name ?? ""));
      if (part) { onSelect(part.name); return; }
      node = node.parent;
    }
    onSelect(null);
  }

  return <>
    <group scale={model.scale}>
      <group position={model.center.clone().multiplyScalar(-1)}>
        <primitive object={model.object} dispose={null} onClick={select} />
        {theme === "dark" && model.rearGlowPosition ? <RearLightGlow position={model.rearGlowPosition} /> : null}
      </group>
    </group>
    <ContactShadows position={[0, -model.dimensions.y * model.scale / 2 - 0.015, 0]} opacity={0.28} scale={14} blur={2.6} far={5} resolution={512} frames={1} color="#111820" />
  </>;
});

function CameraRig({ view, cameraCommand, dimensions, framing = 1.12 }: Pick<SceneProps, "view" | "cameraCommand" | "dimensions" | "framing">) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as OrbitControlsImpl | null;
  const size = useThree((state) => state.size);
  const reset = useRef<() => void>(() => {});
  useEffect(() => {
    const directions = { perspective: [1.6, 0.85, 3.4], side: [0, 0.10, 1], front: [1, 0.10, 0.035] };
    const aspect = size.width / Math.max(1, size.height);
    const bounds: Dimensions = dimensions && Math.max(...dimensions) > 0
      ? dimensions : [4.6, 2.9, 0.9];
    const position = fittedCameraPosition(bounds, new Vector3(...directions[view] as Dimensions), aspect, 37, framing);
    reset.current = () => {
      camera.position.copy(position);
      camera.lookAt(0, 0, 0);
      controls?.target.set(0, 0, 0);
      controls?.update();
    };
    reset.current();
  }, [camera, controls, view, size.width, size.height, dimensions, framing]);
  useEffect(() => {
    if (cameraCommand.kind === "reset") reset.current();
    else {
      const target = controls?.target ?? new Vector3();
      const offset = camera.position.clone().sub(target);
      const distance = Math.min(24, Math.max(1.5, offset.length() * (cameraCommand.kind === "in" ? 0.82 : 1.22)));
      camera.position.copy(target).add(offset.normalize().multiplyScalar(distance));
      controls?.update();
    }
  }, [cameraCommand, camera, controls]);
  return null;
}

export default function BikeScene(props: SceneProps) {
  return <Canvas shadows dpr={[1, 1.75]} performance={{ min: 0.55 }} camera={{ position: [4, 2, 8], fov: 37, near: 0.05, far: 100 }}
    gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
    onPointerMissed={() => props.onSelect(null)}
    fallback={<div className="viewer-notice" role="alert"><strong>3D graphics aren’t available.</strong><p>Try a browser with WebGL enabled.</p></div>}>
    <color attach="background" args={[props.theme === "dark" ? "#171a1b" : "#efefec"]} />
    <ambientLight intensity={0.6} />
    <directionalLight position={[3, 6, 5]} intensity={2.6} color="#fff9f1" castShadow shadow-mapSize={[1024, 1024]} shadow-bias={-0.0002} />
    <directionalLight position={[-4, 2, -3]} intensity={1.3} color="#e2eaff" />
    <Suspense fallback={null}>
      <Environment files={asset(ENVIRONMENT_URL)} environmentIntensity={0.8} />
      <Model {...props} />
    </Suspense>
    <OrbitControls makeDefault regress enableDamping dampingFactor={0.08} minDistance={1.5} maxDistance={24} maxPolarAngle={Math.PI * 0.53} rotateSpeed={0.7} zoomSpeed={0.9} />
    <CameraRig view={props.view} cameraCommand={props.cameraCommand} dimensions={props.dimensions} framing={props.framing} />
    <AdaptiveDpr pixelated />
  </Canvas>;
}
