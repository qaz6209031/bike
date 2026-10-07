"use client";

export type Theme = "light" | "dark";

/** The site is dark-only (the light mode toggle was removed); the type stays for the scene's theme prop. */
export function useTheme(): Theme { return "dark"; }
