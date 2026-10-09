"use client";

import { preload } from "react-dom";
import { asset } from "@/lib/base-path";
import { ENVIRONMENT_URL, MODEL_URL } from "@/lib/parts";

/** Rendered during static export so downloads start before the 3D scene's JavaScript runs. */
export default function AssetPreloads() {
  // Match Three's CORS fetch with same-origin credentials so the loader reuses the response.
  preload(asset(MODEL_URL), { as: "fetch", crossOrigin: "anonymous", fetchPriority: "high" });
  preload(asset(ENVIRONMENT_URL), { as: "fetch", crossOrigin: "anonymous" });
  return null;
}
