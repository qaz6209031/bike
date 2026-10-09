# Repository Guidelines

## Project Structure & Module Organization

This project models the owner's Canyon Endurace in Blender and displays it through Next.js, React Three Fiber, and Three.js.

- `src/app/`: App Router pages, layout, and global styles.
- `src/components/`: viewer controls, scene rendering, and loading UI.
- `src/lib/`: part registry, wheel physics, audio, transforms, and shared utilities.
- `tests/*.test.ts`: automated regression tests.
- `public/`: exported GLB, textures, HDRI, and audio.
- Root Python scripts build, upgrade, and export Blender assets; `scripts/prepare-freehub.py` processes recordings.

## Build, Test, and Development Commands

Use Node.js 22.18 or newer.

- `npm ci`: install dependencies from the lockfile.
- `npm run dev`: start development at `http://localhost:3000`.
- `npm run typecheck`: check TypeScript without emitting files.
- `npm run lint`: run ESLint with Next.js and TypeScript rules.
- `npm test`: run all Node test-runner suites.
- `npm run build`: generate the production static export in `out/`.

Run all four checks before submitting. GitHub Pages CI repeats them. See `README.md` for Blender rebuild/export commands and audio preparation requirements.

## Coding Style & Naming Conventions

Match existing style: two-space indentation, double quotes, and semicolons in TypeScript; four-space indentation in Python. Use strict TypeScript, PascalCase components/types, camelCase functions/variables, and kebab-case source filenames. Use `@/` imports within `src/`; tests import source files with explicit `.ts` extensions. ESLint is configured; no dedicated formatter is configured.

Before changing Next.js code, read the relevant bundled documentation under `node_modules/next/dist/docs/`.

## Testing Guidelines

Tests use `node:test` and `node:assert/strict`. Name files `<feature>.test.ts` and describe observable behavior in test names. Run one suite with `node --experimental-strip-types --test tests/wheel-physics.test.ts`. No numeric coverage threshold is configured. Add regression coverage for physics, audio, transforms, and exported asset changes. Verify visual changes on desktop and phone viewports; compare model renders with reference photos.

## Commit & Pull Request Guidelines

History uses concise, imperative subjects such as `Add black valve caps`, without mandatory prefixes. Keep commits focused. PRs should describe behavior changes, link relevant issues, report checks performed, and include screenshots or comparison renders for visual changes.

## Asset & Configuration Guidelines

Follow `CLAUDE.md` for modeling conventions; preserve photo accuracy, object-name mappings, and axle pivots. Export without overwriting the owner's source blend. Keep private reference photos, videos, Blender files, secrets, and generated build directories untracked. Preserve asset provenance and licenses. Set `NEXT_PUBLIC_BASE_PATH` for subpath deployments.
