# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

A photo-accurate 3D model of the owner's Canyon Endurace CF SLX 7 AXS, built procedurally in Blender and
shown in a Next.js / React Three Fiber web viewer ("Kai’s Bike", live at kaichin.dev/bike). `README.md` covers viewer behaviour,
audio provenance and asset licences.

## Top rule: do NOT simplify anything

The goal is a 3D model that looks like **the owner's actual bike** as closely as possible — not a
generic bike, not a stylised approximation.

- Never replace a real part with a placeholder (plain box, plain cylinder, flat strip, generic blob).
  Model the real shape: profiles, fillets, tapers, cut-outs, teeth, bolts, ribs, textures.
- Never drop a detail because it is small. Logos, prints, bolts, seams, grommets, limit screws,
  tape wraps, hose routing, etc. all belong in the model.
- Match the owner's reference photos, not what a "typical" part looks like. When a photo and general
  product knowledge disagree, the photo wins.
- When a real shape cannot be fully reproduced yet, say exactly what is still off and keep improving it;
  do not quietly settle for an approximation.
- Before claiming a part is done, render it from the same angle as the reference photo and compare.

## Commands

Web viewer (Node.js ≥ 22.18):

```sh
npm ci && npm run dev                                               # http://localhost:3000
npm run typecheck && npm run lint && npm test && npm run build
node --experimental-strip-types --test tests/wheel-physics.test.ts   # one test file
```

Blender pipeline (`BL=/Applications/Blender.app/Contents/MacOS/Blender`):

```sh
python3 make_textures.py                                             # PNG textures (Pillow); before building if changed
python3 extract_canyon_logo.py                                       # CANYON down-tube wordmark -> canyon_glyphs.json
$BL --background --python build_endurace.py -- --size S [--render]  # -> endurace_cf_slx_7_axs_S.blend, render_S_*.png
$BL --background endurace_cf_slx_7_axs_S.blend --python upgrade_studio.py [-- --render --preview --views 34]
$BL --background endurace_cf_slx_7_axs_S_studio.blend --python export_viewer.py   # -> public/models/endurace.glb
python3 scripts/prepare-freehub.py ~/Downloads/sound.MOV            # freehub audio (ffmpeg)
```

To check a part, load the built `.blend` with `--python-expr`, add a camera aimed at the part's bounding-box
centre from the reference photo's angle, render a PNG, and compare it with the matching `*_ref*.jpg`.

## Architecture

### Pipeline

`build_endurace.py` (geometry + EEVEE preview materials) → `upgrade_studio.py` (Cycles studio presentation with
the CC0 HDRI `studio_small_09_2k.hdr`; infers size from the geometry; saves `*_studio.blend`) →
`export_viewer.py` (exports in memory and never overwrites the source blend: curves → meshes, procedural
shaders → baked PBR maps in `public/models/textures/`, part hierarchy + axle pivots, writes
`public/models/endurace.glb`, `manifest.json`, `public/environment/studio.hdr`). The viewer loads the GLB
through `MODEL_URL` in `src/lib/parts.ts`; the exporter updates its `?v=` query from the GLB's content
hash after each successful export. Refresh that hash manually if replacing the GLB without the exporter.

### `build_endurace.py` conventions

- One top-to-bottom script: helpers and materials must be defined **before** the section that uses them
  (past breakages were NameErrors from ordering). `--size` (default `S`) selects `GEOM`, `CRANK_LENGTH`,
  `STEM_LENGTH`.
- Units are mm, converted with `S = 0.001`. +X forward, +Z up, +Y = rider's left; drive side is −Y;
  BB at the origin; axles are `rear` and `front`.
- Every object goes through `add()`, which parents it to the root empty `Endurace_CF_SLX_7_AXS_<SIZE>`;
  `export_viewer.py` only exports direct children of that root.
- **Object-name prefixes are an API.** `export_viewer.main()` assigns objects to viewer groups by prefix
  (`front_wheel_*`/`rear_wheel_*` → wheel or hub, `*_wheel_enve_*` → FrontEnveDecals/RearEnveDecals,
  `pedal_`, `crank_`/`chainring`, `crank_spindle`/`quarq`
  → PowerMeter, `fd_`, `rd_`, `flash_`, `stem`, `gear_groove`, `bryton`, `steerer`/`handlebar`/`bar_`/`hood_`/
  `lever_`/`paddle_`/`shifter_`, `saddle`/`seatpost`, `cage_`, `nametag_` → NameSticker,
  `*_caliper`, `cassette`/`chain`/`cog_`;
  anything else → Frame). Group names must match `PARTS` names or an entry's `objectNames` aliases in
  `src/lib/parts.ts`, and `tests/model-*.test.ts`
  inspect the exported GLB. Keep all three in sync when adding or renaming parts.
- Shape builders: `tube` (bevelled curve), `loft` (superellipse sections), `ribbon` (flat strap), `sweep`
  (oval section, rotation-minimising frame, UVs), `extrude_profile` (2D loops with holes, e.g. `sprocket_loop`
  teeth, rotor slots), `box`, `cyl`.
- Decals are flat meshes (`text_bmesh`, `rect_bmesh`, `shapes_bmesh`) wrapped onto **analytic** surfaces by
  mapping functions (`tube_map` with radius `knots`, `ring_map`, `seat_tube_map`, `ht_front_map`). Changing a
  tube's shape means updating its mapping, or decals sink or float. PNG-based decals (ENVE, Schwalbe, Bryton)
  use `mask_mat`/`print_mat`/`image_mat` with `uv=`.
- `fuse()` voxel-remeshes and volume-preserving-smooths named objects into one filleted surface
  (`front_triangle` = head tube + tube stubs, `fork`, `rear_triangle`, `stem_tbar` = stem + bar tops). The exporter
  cuts the finished `stem_tbar` surface at its `barRearX` property into `stem_tbar` (Stem group) and
  `handlebar_tbar_tops` (Cockpit), keeping the original normals, so the viewer can highlight the stem alone. Keep decal-carrying tubes (`down_tube`,
  `top_tube`) outside fusions; a decal on a fused surface needs a shrinkwrap (see the head-tube logo).
- The frame line (`P_TOP`, `tt_u`, `FRAME_N`) drives the seat-tube top cut, collar and name tag via `cut_to_plane`.

### Web viewer (`src/`)

`src/lib/parts.ts` is the part registry (names, labels, specs, the owner-upgrade panel order, URLs).
`src/components/bike-scene.tsx` renders the GLB; wheel groups rotate about their origins using the GLB extras
`pivotAtAxle` / `wheelAxis` (Blender +Z up → glTF +Y; axle → Z). `src/lib/wheel-physics.ts` integrates
frame-rate-independent exponential damping; `src/lib/freehub-audio.ts` plays the owner's recording;
`src/lib/freehub-recording.ts` is generated by `scripts/prepare-freehub.py`.

`src/components/model-loading.tsx` renders the loading overlay in the viewer shell's DOM outside the
Canvas; the Canvas's asset Suspense boundary uses `fallback={null}`. Do not use drei `Html` for this
loading fallback: its separate React root can race with Suspense cleanup. `src/lib/loading-progress.ts`
defers loader notifications to a microtask so GLB loading cannot update the overlay during render, and
unsubscribes/cancels pending notifications on unmount.

## Files

- `canyon_glyphs.json` — the CANYON down-tube wordmark as upright vector outlines (mm), traced from the owner's
  photo `canyonlogo_ref_1.jpg` by `extract_canyon_logo.py` (`logo.avif` = Canyon product image, used for scale).
  `canyon_wordmark()` in the builder shears it onto the tube at the model's down-tube angle so strokes stay level,
  mirroring the shear on the non-drive side. Never replace it with a system font.
- `endurace_glyphs.json` — ENDURACE SLX top-tube decal, traced from `slx_ref.jpg` (`python3 extract_canyon_logo.py --endurace`),
  meshed with letter counters as holes by `glyph_decal()`. Never replace it with a system font either.
- `*_ref*.jpg` — the owner's reference photos, one set per part (saddle, cages, shifters, derailleurs,
  chain/drivetrain, brakes/hoses, hubs, head tube, bar, stickers, light, dropouts…). New photos usually arrive
  in `~/Downloads` (newest by modification time; names can contain spaces, e.g. `IMG_6938 2.JPG`).
- `render_<SIZE>_*.png` — renders used to check parts against the photos.
- The size M `.blend`, `.blend1` backup and `_M_studio.blend` are older builds. `public/models/endurace.glb`
  is exported from the owner's updated `endurace_cf_slx_7_axs_S.blend`: size S geometry, 322 mesh objects,
  and a 1008 mm wheelbase. Preserve that source file when exporting; do not rebuild it to update the viewer.

## Owner's bike (as built)

- Frame: Canyon Endurace CF SLX, size S, Crystal White; CANYON down tube, ENDURACE SLX top tube,
  Canyon "mountain" head-tube logo, custom Taiwan-flag "Kai" name tag under the seatpost collar.
- Groupset: SRAM Rival eTap AXS 2x12 (48/35T, 10-36), SRAM DUB PM Spindle power meter, Rival AXS hoods/levers/paddles.
- Wheels: Canyon ED42 CF carbon rims with white ENVE stickers (decals, not ENVE wheels), DT Swiss 350 hubs with rear ratchet upgraded from 36T to 54T,
  Schwalbe Pro One Evo 32mm tyres, SRAM Paceline 160mm rotors, SRAM flat-mount calipers,
  internally routed hoses (fork leg / chainstay ports).
- Cockpit: Canyon PACE T-bar (flat aero tops, taped), 80 mm stem (owner's specification), Bryton S510 on a GEAR GROOVE mount.
- Seat: Fizik Aliante R5 on SP0093 VCLS Aero post; Canyon FLASH rear light. The post is matte black with no white
  print on the shaft (only a dark-grey SP093 on the non-drive side and white "5 Nm" on the head): a slim rear leaf
  sweeps back into the set-back clamp head, the front ~2/3 is a ribbed VCLS elastomer panel (`seattube_ref.jpg`).
  Clamp bolt 629.5 mm up the seat axis, 10 mm setback; saddle 2.2 deg nose-down — back-projected from `bike_ref.jpg`
  through the axle centres, which is how to measure any part's position from that photo.
- Pedals: Shimano PD-R550. Cages: HUALONG 3K Carbon Fiber Bicycle Water Bottle Cage, X-style (same model) on down tube (adapter plate)
  and seat tube.
- Website Upgrades lists only these nine owner additions, in order: Canyon FLASH Cycling Rear Light; Canyon PACE T-bar with 80 mm stem; HUALONG cages; Bryton S510; Canyon GEAR GROOVE Computer Mount; 36T-to-54T freehub upgrade; Shimano PD-R550 pedals; VeloInk name sticker (veloink.com); white ENVE rim decal stickers. The EnveDecals registry entry maps to both FrontEnveDecals and RearEnveDecals; keep those groups parented to their own wheel pivots. Keep the remaining stock parts addressable in the model without listing them in the panel. The owner requested removal of the geometry notice from the page.

## Workflow

- The model opens in Material Preview (decals/textures are invisible in Solid shading).
- After rebuilding, an open Blender session must reload the file (File → Revert) to show changes.
