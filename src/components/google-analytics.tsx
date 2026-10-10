import Script from "next/script";
import { ANALYTICS_BOOTSTRAP, GA_MEASUREMENT_ID } from "@/lib/analytics";

export default function GoogleAnalytics() {
  if (process.env.NODE_ENV !== "production") return null;

  return <>
    <Script id="bike-google-analytics-init" strategy="afterInteractive">{ANALYTICS_BOOTSTRAP}</Script>
    <Script id="bike-google-analytics" src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`} strategy="afterInteractive" />
  </>;
}
