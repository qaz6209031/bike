import test from "node:test";
import assert from "node:assert/strict";
import { runInNewContext } from "node:vm";
import { ANALYTICS_BOOTSTRAP, GA_MEASUREMENT_ID, isLiveBikeSite, trackBikeEvent } from "../src/lib/analytics.ts";

const locations = [
  ["kaichin.dev", "/bike", true],
  ["kaichin.dev", "/bike/", true],
  ["kaichin.dev", "/bike/details/", true],
  ["kaichin.dev", "/", false],
  ["kaichin.dev", "/bike-shop/", false],
  ["kaichin.dev", "/other/bike/", false],
  ["localhost", "/bike/", false],
  ["127.0.0.1", "/bike/", false],
  ["qaz6209031.github.io", "/bike/", false],
  ["kaichin.dev.example.com", "/bike/", false],
] as const;

test("the tag and event dispatcher only accept the live bike site", () => {
  for (const [hostname, pathname, active] of locations) {
    assert.equal(isLiveBikeSite(hostname, pathname), active, `${hostname}${pathname}`);
    const window = { location: { hostname, pathname } } as {
      location: { hostname: string; pathname: string };
      dataLayer?: IArguments[];
    };
    runInNewContext(ANALYTICS_BOOTSTRAP, { window });
    assert.equal(Boolean(window.dataLayer), active, `${hostname}${pathname}`);
    if (active) {
      assert.equal(window.dataLayer?.length, 2, "initialize only one config (automatic page view)");
      const config = window.dataLayer?.[1];
      assert.equal(config?.[0], "config");
      assert.equal(config?.[1], GA_MEASUREMENT_ID);
      assert.equal(config?.[2].allow_google_signals, false);
      assert.equal(config?.[2].allow_ad_personalization_signals, false);
    }
  }
});

function withBrowser(mode: string, hostname: string, pathname: string, callback: (calls: unknown[][]) => void, blocked = false) {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const envName: string = "NODE_ENV";
  const previousMode = process.env[envName];
  const calls: unknown[][] = [];
  const window = { location: { hostname, pathname }, ...(blocked ? {} : { gtag: (...args: unknown[]) => calls.push(args) }) };
  Object.defineProperty(globalThis, "window", { configurable: true, value: window });
  process.env[envName] = mode;
  try { callback(calls); }
  finally {
    if (previousMode === undefined) delete process.env[envName];
    else process.env[envName] = previousMode;
    if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow);
    else Reflect.deleteProperty(globalThis, "window");
  }
}

test("wheel and upgrade events contain only their controlled fields", () => {
  withBrowser("production", "kaichin.dev", "/bike/", (calls) => {
    const event = { name: "wheel_spin", wheel: "RearWheel", rpm: 180, unexpected: "private-data" } as const;
    trackBikeEvent(event);
    trackBikeEvent({ name: "wheel_spin", wheel: "both", rpm: 240 });
    trackBikeEvent({ name: "upgrade_select", part: "RearLight" });
    assert.deepEqual(calls, [
      ["event", "wheel_spin", { wheel: "RearWheel", rpm: 180, send_to: GA_MEASUREMENT_ID }],
      ["event", "wheel_spin", { wheel: "both", rpm: 240, send_to: GA_MEASUREMENT_ID }],
      ["event", "upgrade_select", { part: "RearLight", send_to: GA_MEASUREMENT_ID }],
    ]);
  });
});

test("development and other sites never dispatch custom events", () => {
  for (const mode of ["development", "production"]) {
    for (const [hostname, pathname, active] of locations) {
      withBrowser(mode, hostname, pathname, (calls) => {
        trackBikeEvent({ name: "wheel_spin", wheel: "FrontWheel", rpm: 90 });
        assert.equal(calls.length, mode === "production" && active ? 1 : 0);
      });
    }
  }
});

test("blocked analytics cannot interrupt the viewer interaction", () => {
  withBrowser("production", "kaichin.dev", "/bike/", () => {
    assert.doesNotThrow(() => trackBikeEvent({ name: "wheel_spin", wheel: "RearWheel", rpm: 180 }));
  }, true);
});
