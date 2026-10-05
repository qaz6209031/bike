type ProgressStore = {
  getState: () => { progress: number };
  subscribe: (listener: () => void) => () => void;
};

/** Three loaders can publish during render; notify React after that render finishes. */
export function watchLoadingProgress(store: ProgressStore, onProgress: (progress: number) => void) {
  let active = true;
  let queued = false;
  const schedule = () => {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (active) onProgress(store.getState().progress);
    });
  };
  const unsubscribe = store.subscribe(schedule);
  schedule();
  return () => {
    active = false;
    unsubscribe();
  };
}
