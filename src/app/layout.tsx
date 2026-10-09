import type { Metadata, Viewport } from "next";
import { THEME_BOOTSTRAP } from "@/lib/theme-config";
import AssetPreloads from "@/components/asset-preloads";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kai’s Bike — Canyon Endurace CF SLX in 3D",
  description: "Kai’s Canyon Endurace CF SLX in interactive 3D. Explore every component, spin the wheels, and hear the freehub coast.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#171a1b", colorScheme: "dark" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" data-theme="dark" style={{ colorScheme: "dark" }} suppressHydrationWarning><head><AssetPreloads /><script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} /></head><body>{children}</body></html>;
}
