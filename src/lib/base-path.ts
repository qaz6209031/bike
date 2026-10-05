// Sub-path the site is served from (e.g. "/endurace" for kaichin.dev/endurace); "" at a domain root.
// Set NEXT_PUBLIC_BASE_PATH at build time; next.config.ts uses the same value for basePath.
export const BASE_PATH = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");

/** Prefix a root-relative public asset path ("/models/…") with the deployment base path. */
export const asset = (path: string) => `${BASE_PATH}${path}`;
