import type { CSSProperties } from "react";

const paths = {
  orbit: <><ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-35 12 12)" /><circle cx="12" cy="12" r="2" /></>,
  wheel: <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2" /><path d="M12 3v7m0 4v7M3 12h7m4 0h7M5.6 5.6l5 5m2.8 2.8 5 5M5.6 18.4l5-5m2.8-2.8 5-5" /></>,
  bike: <><circle cx="5.5" cy="16.5" r="4" /><circle cx="18.5" cy="16.5" r="4" /><path d="m5.5 16.5 5-8 4 8h-9l7-6m2-6h3l2 12M8 8h5" /></>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
  reset: <><path d="M3 10a9 9 0 1 1 .8 7M3 4v6h6" /></>,
  plus: <path d="M5 12h14M12 5v14" />,
  minus: <path d="M5 12h14" />,
  sound: <><path d="m11 4-6 5H2v6h3l6 5V4Zm4 4a6 6 0 0 1 0 8m3-11a10 10 0 0 1 0 14" /></>,
  mute: <><path d="m11 4-6 5H2v6h3l6 5V4Zm5 5 6 6m0-6-6 6" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  chevron: <path d="m9 5 7 7-7 7" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10v.1" /></>,
  brake: <><path d="M8 5v14M16 5v14" /><circle cx="12" cy="12" r="9" /></>,
  hand: <><path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11m0-6.5V3.5a1.5 1.5 0 0 1 3 0V11m0-6a1.5 1.5 0 0 1 3 0v6m0-3.5a1.5 1.5 0 0 1 3 0V15a7 7 0 0 1-7 7h-1.2a6 6 0 0 1-4.6-2.1l-3.5-4.2a1.6 1.6 0 0 1 2.4-2.1L8 15.5" /></>,
  rotate: <><rect x="3" y="7" width="18" height="11" rx="2" transform="rotate(-90 12 12.5)" /><path d="M17 3.5a8 8 0 0 1 3.5 5.5m0 0 1.5-2.5M20.5 9l-2.7-.6" /></>,
} as const;

export default function Icon({ name, size = 18, style }: { name: keyof typeof paths; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}>{paths[name]}</svg>;
}
