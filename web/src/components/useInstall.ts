"use client";

import { useCallback, useEffect, useState } from "react";

type BeforeInstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
export type InstallState = { installed: boolean; canInstall: boolean; platform: "android" | "ios" | "desktop"; prompt: () => Promise<boolean> };

/** Registers the service worker and exposes the "Add to home screen" prompt where the browser offers one. */
export function useInstall() {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [online, setOnline] = useState(() => navigator.onLine);
  // Kettu renders client-only, so the browser can be asked directly.
  const [installed, setInstalled] = useState(
    () =>
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true,
  );
  const [platform] = useState<"android" | "ios" | "desktop">(() => {
    const ua = navigator.userAgent;
    return /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
      ? "ios" : /Android/.test(ua) ? "android" : "desktop";
  });

  useEffect(() => {
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch(() => undefined);
    }
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setDeferred(null);
    };
    const display = window.matchMedia("(display-mode: standalone)");
    const onDisplay = () => { if (display.matches) setInstalled(true); };
    const connection = () => setOnline(navigator.onLine);
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    display.addEventListener("change", onDisplay);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
      display.removeEventListener("change", onDisplay);
    };
  }, []);

  const prompt = useCallback(async () => {
    if (!deferred) return false;
    setDeferred(null);
    try { await deferred.prompt(); await deferred.userChoice; return true; }
    catch { return false; }
  }, [deferred]);

  return { canInstall: Boolean(deferred), installed, platform, prompt, online };
}
