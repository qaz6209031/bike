import type { NextConfig } from "next";

// Static export for GitHub Pages. NEXT_PUBLIC_BASE_PATH is the sub-path the site is served from
// ("/endurace" for kaichin.dev/endurace); leave it unset to serve from a domain root.
const basePath = (process.env.NEXT_PUBLIC_BASE_PATH ?? "").replace(/\/$/, "");

const config: NextConfig = {
  reactStrictMode: true,
  output: "export",
  basePath: basePath || undefined,
  trailingSlash: true,
  images: { unoptimized: true },
};

export default config;
