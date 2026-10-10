# Kai’s Bike

A browser-based viewer for the owner's Canyon Endurace CF SLX 7 AXS, built with Next.js App Router, React, React Three Fiber, drei, and Three.js.

## Run

Use Node.js 22.18 or newer.

```sh
npm ci
npm run dev
```

Open <http://localhost:3000>. For a production build, run `npm run build` followed by `npm start`.

## Viewer

- A self-contained size S bike export is included at `public/models/endurace.glb` (322 mesh objects), exported from the owner's updated `endurace_cf_slx_7_axs_S.blend`. It retains the detailed geometry and decals.
- A responsive full-bike Canvas, ambient/directional lights, a local studio HDRI, contact shadows, and physically based materials.
- Light/dark mode follows your system preference initially and remembers your toggle choice. The 3D background changes with the interface, and the rear light gains a subtle red halo and nearby illumination in dark mode.
- Build specifications are for size S, using the [Canyon component section](https://www.canyon.com/en-us/road-bikes/endurance-bikes/endurace/cf-slx/endurace-cf-slx-7-axs/4431.html?dwvar_4431_pv_rahmenfarbe=R130_P01) and the owner's corrections. The personal build has an 80 mm stem, 165 mm cranks, SRAM DUB PM Spindle power meter, Bryton S510 computer, and HUALONG 3K Carbon Fiber Bicycle Water Bottle Cages. Wheels are Canyon ED42 CF with ENVE stickers and a rear-hub ratchet upgraded from 36T to 54T.
- The Upgrades panel lists only the owner's nine additions, in their requested order: Canyon FLASH Cycling Rear Light; Canyon PACE T-bar with 80 mm stem; HUALONG cages; Bryton S510; Canyon GEAR GROOVE Computer Mount; 54T freehub upgrade; Shimano PD-R550 pedals; [VeloInk name sticker](https://veloink.com/); white ENVE rim decal stickers. Stock parts remain addressable and the wheel controls use the complete object registry.
- Drag or use one finger to orbit; pinch/scroll to zoom; two fingers or the right mouse button to pan. Camera presets, zoom buttons, and reset are also available.
- Phone layouts show only the wheel controls beneath the viewer; the Upgrades list stays on desktop. Mobile controls have larger touch targets, a single column, and notch-safe spacing, with a shortcut beneath the viewer to jump to Wheel controls. The camera fits the usable Canvas area between the heading and controls, including after rotation to landscape.
- Click an upgrade/accessory or select it in the Upgrades panel. Only owner additions actually present in the loaded model appear.
- Choose front, rear, or both wheels, set spin speed, then click **Spin wheel**. Fixed background friction slows the wheels to rest; there is no friction control. **Brake** stops both wheels immediately.
- Freehub sound is enabled automatically when clicking **Spin wheel** on desktop or **Spin rear wheel** on a phone. A continuous coasting recording plays once at its original pitch and stereo balance; its recorded click cadence falls naturally and volume also falls with rear-wheel RPM. It never wraps back to a louder section during the same coast. It fades near a stop and stops in background tabs.
- Loading progress, a recoverable GLB error boundary, audio-load errors, and a WebGL fallback are included. The loading overlay lives in the page's DOM outside the Canvas. Loader progress notifications are deferred until after rendering and cancelled when the overlay unmounts.

## Named parts and axle pivots

The export includes `Frame`, `FrontWheel`, `RearWheel`, `FrontHub`, `RearHub`, `Crank`, `Pedals`, `PowerMeter`, `RearLight`, `FrontDerailleur`, `RearDerailleur`, `Cockpit`, `Stem`, `BikeComputer`, `ComputerMount`, `Saddle`, `BottleCages`, `Brakes`, `Drivetrain`, and `NameSticker`. `NameSticker` groups both existing Kai/Taiwan flag decals under the frame. `FrontLight` is supported by the viewer registry but is absent from the source bike.

The wheel groups have origins at the axle centres, with `extras.pivotAtAxle = true` and `extras.wheelAxis = [0, 0, 1]`. Blender’s vertical Z axis becomes glTF’s Y axis; the axle becomes Z. Hubs, rotors, spokes, rims, tyres, and their decals rotate together. `FrontEnveDecals` and `RearEnveDecals` stay inside their respective wheels, and the viewer selects both through the single `EnveDecals` upgrade. Through axles, calipers, chain, and cassette remain stationary while coasting.

`src/lib/wheel-physics.ts` integrates exponential angular damping exactly, independent of frame rate, with a fixed coefficient of 0.12 s⁻¹ and a 0.025 rad/s stop threshold. Friction is half the previous value: a wheel launched at 180 RPM now coasts for about 55 seconds instead of 28. The threshold's crossing time also limits angular travel, so stopping remains independent of frame rate. Friction is internal tuning and has no setter or UI control. Velocity is in radians per second; the UI converts RPM. Transient motion stays outside React state, with `useFrame` applying wheel transforms and a throttled UI readout.

For future pointer/touch flick recognition, feed the estimated angular impulse into the same controller:

```ts
drive.addImpulse("RearWheel", deltaRadiansPerSecond);
// Or set an absolute velocity:
drive.setVelocity("RearWheel", rpmToRadians(180));
```

## Re-export from Blender

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --python build_endurace.py -- --size S

/Applications/Blender.app/Contents/MacOS/Blender \
  --background endurace_cf_slx_7_axs_S.blend \
  --python upgrade_studio.py

/Applications/Blender.app/Contents/MacOS/Blender \
  --background endurace_cf_slx_7_axs_S_studio.blend \
  --python export_viewer.py
```

The script exports in memory without changing the source blend. It preserves curves as evaluated meshes, creates the addressable part hierarchy and axle pivots, converts procedural finishes to web PBR textures, embeds decals, and writes the GLB, manifest, and HDRI to `public/`. It refreshes `MODEL_URL` with the exported file's content hash so the viewer loads the new model after each export. It preserves any existing freehub audio; a synthetic fallback is created only when the audio file is missing.

The exporter also runs `scripts/compress-model.ts` using Node.js 22.18 or newer; run `npm ci` before exporting. This applies lossless `EXT_meshopt_compression` and compares every decoded buffer with the original before replacing the GLB. Vertex values, index order, textures, materials, named parts, and axle pivots are preserved without quantization or simplification. The current model shrinks from 36.5 MB to 20.3 MB. To compress an existing export without opening Blender, run `npm run compress:model`; repeated runs leave already compressed assets unchanged and refresh the model URL's content hash.

The static HTML preloads the model and studio HDRI using the same URLs and CORS settings as Three's loaders, including `NEXT_PUBLIC_BASE_PATH`, so their downloads can start before the viewer's JavaScript runs. Audio still loads only after interaction.

The original size M `.blend` and upgraded `_studio.blend` are retained as older builds. The web asset uses the owner's updated size S `.blend`. To export that file again without rebuilding it, run Blender with `--background endurace_cf_slx_7_axs_S.blend --python-exit-code 1 --python export_viewer.py`. The exporter applies the studio finishes in memory when needed and preserves the source file and existing freehub audio. The builder defaults to size S, with size-specific frame geometry, crank length, and stem length. `upgrade_studio.py` infers size from the loaded geometry and rejects a conflicting `--size` argument; use `--render --preview --views 34` to render a proof.

To use another GLB, replace `public/models/endurace.glb` or change `MODEL_URL` in `src/lib/parts.ts`. `BikeScene` also accepts a `url` prop. Give important groups the names above; keep wheel group origins at the axle and specify `wheelAxis` in each group’s local coordinates. An unmarked wheel receives a fallback pivot at its geometry bounds centre.

## Audio and asset licences

`public/audio/freehub.wav` uses the replacement 43.9 second recording from `~/Downloads/sound.MOV`. After excluding the first two seconds of handling, the entire remaining 41.924 second coast retains its original stereo channels, 48 kHz sample rate, and level. There is no EQ, mono conversion, resampling, normalization, crossfade, or repetition. The video is unchanged and is not copied to `public/`. Source and audio hashes and processing details are in `public/audio/freehub.json`; no CC0 licence is asserted for the owner's recording.

Recreate it with `python3 scripts/prepare-freehub.py ~/Downloads/sound.MOV` (requires ffmpeg). The script accepts `--start` and an optional `--duration` for choosing another take. It also generates `src/lib/freehub-recording.ts` with a content hash in the audio URL, so a replacement bypasses cached audio. Fetches use `cache: "no-store"`.

Playback remains at 1× to retain the recorded freehub's tone and natural deceleration. Gain uses 180 RPM as the full-volume reference. Enabling sound mid-coast starts later in the recording, using the wheel's exponential decay to estimate elapsed coast time. This is studio synchronization, not a measured RPM calibration of the source video. After the take ends it stays silent while RPM keeps falling; increasing the wheel's speed can start a new take. The viewer still requires a click/tap to enable sound. Reload an already-open viewer after replacing its recording to clear the decoded audio buffer.

The HDRI is [Studio Small 09](https://polyhaven.com/a/studio_small_09) by Sergej Majboroda, licensed [CC0 by Poly Haven](https://polyhaven.com/license). Its local copy is `public/environment/studio.hdr` and the source file is `studio_small_09_2k.hdr`. Carbon and rubber maps are generated locally by the exporter. The browser does not depend on an external model, audio, texture, or environment CDN.

## Analytics

Google Analytics 4 uses the **Kai’s Bike** property and **Kai’s Bike Web** stream
(`G-92G5KNHSB8`). No extra environment variable is needed. The tag loads after
hydration in production exports and only collects on `kaichin.dev/bike/` (and its
subpages), excluding localhost, previews, and the rest of `kaichin.dev`.

GA4 automatically reports visits, engagement, device categories (desktop/mobile/tablet),
scrolls, and outbound clicks. Custom `wheel_spin` events include the wheel and launch
RPM, and `upgrade_select` events include the selected part name. The phone and desktop
spin controls both send the same event. Audio and model contents are never sent.
Google signals and ad personalization signals are disabled.
The property has event-scoped custom dimensions for **Wheel** (`wheel`),
**Upgrade part** (`part`), and **Launch RPM** (`rpm`) for use in reports and explorations.

After deploying, visit `https://kaichin.dev/bike/`, spin a wheel or select an upgrade,
and check the **Kai’s Bike → Reports → Realtime** report. Device categories appear
under **Reports → User → Tech**.

## Checks

```sh
npm run typecheck
npm run lint
npm test
npm run build
```

Tests cover frame-rate-independent decay and stopping, braking, separate wheel control, actual exported tyre centres under axle rotation, fallback pivots, camera framing on portrait screens, stationary drivetrain/brakes, complete embedded model assets, native recording provenance, audio activation order, falling volume without recording restarts, mid-coast sound activation, muting, visibility changes, audio-load failure, deferred loading progress, and loading-overlay cleanup under Strict Mode.

Browser verification still needs a normal local run: this workspace sandbox prevents binding a development-server port. Blender 5.2.2 also crashes during Metal initialization here, before it can rebuild or export. Check theme switching and persistence, orbit/pinch/zoom, selection, spinning and braking, sound activation, a missing GLB, and a phone-sized viewport when running locally.
