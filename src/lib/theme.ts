"use client";

import { useSyncExternalStore } from "react";
import { THEME_EVENT, THEME_KEY } from "./theme-config";

export type Theme = "light" | "dark";

function getSnapshot(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function getServerSnapshot(): Theme { return "light"; }

export function setTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* Private browsing can restrict storage. */ }
  window.dispatchEvent(new Event(THEME_EVENT));
}

function subscribe(listener: () => void) {
  const preference = window.matchMedia("(prefers-color-scheme: dark)");
  const syncPreference = () => {
    let saved: string | null = null;
    try { saved = localStorage.getItem(THEME_KEY); } catch { /* Use the system preference. */ }
    const next = saved === "light" || saved === "dark" ? saved : preference.matches ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    document.documentElement.style.colorScheme = next;
    listener();
  };
  const storageChanged = (event: StorageEvent) => { if (event.key === THEME_KEY || event.key === null) syncPreference(); };
  window.addEventListener(THEME_EVENT, listener);
  window.addEventListener("storage", storageChanged);
  preference.addEventListener("change", syncPreference);
  return () => {
    window.removeEventListener(THEME_EVENT, listener);
    window.removeEventListener("storage", storageChanged);
    preference.removeEventListener("change", syncPreference);
  };
}

export function useTheme() { return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot); }
