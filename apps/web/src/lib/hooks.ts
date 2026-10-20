"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

import { errorMessage, isAbort } from "@/lib/api";

type LoadState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  refreshing: boolean;
};

/**
 * Loads data from the API with an abortable request and manual reload.
 * `deps` controls refetching; pass stable primitives.
 */
export function useApiData<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: unknown[] = [],
) {
  const loaderRef = useRef(loader);
  useEffect(() => {
    loaderRef.current = loader;
  }, [loader]);

  const [state, setState] = useState<LoadState<T>>({
    data: null,
    error: null,
    loading: true,
    refreshing: false,
  });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    // Request lifecycle state (loading/refreshing) intentionally lives in React
    // state so the UI can distinguish the first load from a background refresh.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setState((previous) => ({
      ...previous,
      error: null,
      loading: previous.data === null,
      refreshing: previous.data !== null,
    }));

    loaderRef
      .current(controller.signal)
      .then((data) => {
        if (!active) return;
        setState({ data, error: null, loading: false, refreshing: false });
      })
      .catch((error: unknown) => {
        if (!active || isAbort(error)) return;
        setState((previous) => ({
          ...previous,
          error: errorMessage(error),
          loading: false,
          refreshing: false,
        }));
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version, ...deps]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  const setData = useCallback(
    (data: T) => setState({ data, error: null, loading: false, refreshing: false }),
    [],
  );

  return { ...state, reload, setData };
}

export function useDebouncedValue<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function subscribeOnline(callback: () => void): () => void {
  window.addEventListener("online", callback);
  window.addEventListener("offline", callback);
  return () => {
    window.removeEventListener("online", callback);
    window.removeEventListener("offline", callback);
  };
}

export function useOnlineStatus(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

export function useAutoRefresh(callback: () => void, intervalMs: number, enabled: boolean) {
  const callbackRef = useRef(callback);
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);
  useEffect(() => {
    if (!enabled) return;
    const timer = window.setInterval(() => callbackRef.current(), intervalMs);
    return () => window.clearInterval(timer);
  }, [enabled, intervalMs]);
}

type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
};

function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function subscribeInstalled(callback: () => void): () => void {
  const media = window.matchMedia("(display-mode: standalone)");
  window.addEventListener("appinstalled", callback);
  media.addEventListener("change", callback);
  return () => {
    window.removeEventListener("appinstalled", callback);
    media.removeEventListener("change", callback);
  };
}

export function useInstallPrompt() {
  const [promptEvent, setPromptEvent] = useState<InstallPromptEvent | null>(null);
  const installed = useSyncExternalStore(subscribeInstalled, isStandalone, () => false);

  useEffect(() => {
    const onPrompt = (event: Event) => {
      event.preventDefault();
      setPromptEvent(event as InstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const promptInstall = useCallback(async (): Promise<"accepted" | "dismissed" | "unavailable"> => {
    if (!promptEvent) return "unavailable";
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    setPromptEvent(null);
    return choice.outcome;
  }, [promptEvent]);

  return { canInstall: Boolean(promptEvent), installed, promptInstall };
}

export function useServiceWorkerReady(): boolean | null {
  const [ready, setReady] = useState<boolean | null>(() =>
    typeof navigator !== "undefined" && "serviceWorker" in navigator ? null : false,
  );
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    let active = true;
    navigator.serviceWorker
      .getRegistration()
      .then((registration) => {
        if (active) setReady(Boolean(registration?.active));
      })
      .catch(() => {
        if (active) setReady(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return ready;
}
