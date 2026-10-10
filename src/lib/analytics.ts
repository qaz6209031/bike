import type { PartName } from "./parts.ts";
import type { WheelTarget } from "./wheel-physics.ts";

export const GA_MEASUREMENT_ID = "G-92G5KNHSB8";
const LIVE_HOSTNAME = "kaichin.dev";
const LIVE_PATH = "/bike";

export function isLiveBikeSite(hostname: string, pathname: string): boolean {
  return hostname === LIVE_HOSTNAME && (pathname === LIVE_PATH || pathname.startsWith(`${LIVE_PATH}/`));
}

export const ANALYTICS_BOOTSTRAP = `
  if (window.location.hostname === ${JSON.stringify(LIVE_HOSTNAME)} &&
      (window.location.pathname === ${JSON.stringify(LIVE_PATH)} ||
       window.location.pathname.startsWith(${JSON.stringify(`${LIVE_PATH}/`)}))) {
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag('js', new Date());
    window.gtag('config', '${GA_MEASUREMENT_ID}', {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }
`;

type BikeAnalyticsEvent =
  | { name: "wheel_spin"; wheel: WheelTarget; rpm: number }
  | { name: "upgrade_select"; part: PartName };

declare global {
  interface Window {
    gtag?: (command: "event", name: BikeAnalyticsEvent["name"], parameters: Record<string, string | number>) => void;
  }
}

/** Only controlled viewer values are sent; never URLs, audio, or model contents. */
export function trackBikeEvent(event: BikeAnalyticsEvent) {
  if (process.env.NODE_ENV !== "production" || typeof window === "undefined" ||
      !isLiveBikeSite(window.location.hostname, window.location.pathname)) return;

  const parameters: Record<string, string | number> = event.name === "wheel_spin"
    ? { wheel: event.wheel, rpm: event.rpm }
    : { part: event.part };
  window.gtag?.("event", event.name, { ...parameters, send_to: GA_MEASUREMENT_ID });
}
