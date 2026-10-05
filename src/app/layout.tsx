import type { Metadata, Viewport } from "next";
import { THEME_BOOTSTRAP } from "@/lib/theme-config";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kai’s Bike — Canyon Endurace CF SLX in 3D",
  description: "Kai’s Canyon Endurace CF SLX in interactive 3D. Explore every component, spin the wheels, and hear the freehub coast.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: [{ media: "(prefers-color-scheme: light)", color: "#f8f8f5" }, { media: "(prefers-color-scheme: dark)", color: "#171a1b" }] };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><head><script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} /></head><body>{children}</body></html>;
}
