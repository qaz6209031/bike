import test from "node:test";
import assert from "node:assert/strict";
import { watchLoadingProgress } from "../src/lib/loading-progress.ts";

function progressStore() {
  let progress = 0;
  const listeners = new Set<() => void>();
  return {
    getState: () => ({ progress }),
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    publish(value: number) {
      progress = value;
      for (const listener of listeners) listener();
    },
    get subscribers() { return listeners.size; },
  };
}

test("a loader publishing during render never updates the loading UI synchronously", async () => {
  const store = progressStore();
  const values: number[] = [];
  const unsubscribe = watchLoadingProgress(store, (progress) => values.push(progress));
  try {
    await Promise.resolve();
    assert.deepEqual(values, [0]);
    store.publish(25);
    store.publish(75);
    assert.deepEqual(values, [0], "React state must not update inside the loader's render");
    await Promise.resolve();
    assert.deepEqual(values, [0, 75], "one deferred update reads the latest progress");
    store.publish(100);
    await Promise.resolve();
    assert.deepEqual(values, [0, 75, 100]);
  } finally { unsubscribe(); }
});

test("unmounting with a progress update queued never updates the removed UI", async () => {
  const store = progressStore();
  const values: number[] = [];
  const unsubscribe = watchLoadingProgress(store, (progress) => values.push(progress));
  store.publish(50);
  unsubscribe();
  assert.equal(store.subscribers, 0);
  await Promise.resolve();
  store.publish(100);
  await Promise.resolve();
  assert.deepEqual(values, []);
});

test("Strict Mode cleanup and remount leave only the current loading UI subscribed", async () => {
  const store = progressStore();
  const removed: number[] = [];
  const current: number[] = [];
  const cleanup = watchLoadingProgress(store, (progress) => removed.push(progress));
  cleanup();
  const unsubscribe = watchLoadingProgress(store, (progress) => current.push(progress));
  try {
    store.publish(100);
    await Promise.resolve();
    assert.deepEqual(removed, []);
    assert.deepEqual(current, [100]);
    assert.equal(store.subscribers, 1);
  } finally { unsubscribe(); }
});
