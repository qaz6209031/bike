"use client";

import { useEffect, useState } from "react";
import { useProgress } from "@react-three/drei";
import { watchLoadingProgress } from "@/lib/loading-progress";

export default function ModelLoading() {
  const [progress, setProgress] = useState(0);
  useEffect(() => watchLoadingProgress(useProgress, setProgress), []);
  const percent = Number.isFinite(progress) ? Math.round(Math.min(100, Math.max(0, progress))) : 0;
  return <div className="viewer-notice canvas-loading" role="status" aria-live="polite">
    <span className="loading-ring" /><strong>Preparing your ride</strong><span>{percent}% loaded</span>
  </div>;
}
