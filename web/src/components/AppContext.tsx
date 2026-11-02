"use client";

import { createContext, useContext, type RefObject } from "react";
import type { T } from "@/lib/i18n";
import type { Prefs } from "@/lib/prefs";
import type { InstallState } from "./useInstall";

export type AppCtx = {
  t: T;
  prefs: Prefs;
  setPrefs: (p: Partial<Prefs>) => void;
  device: string;
  dialogTrigger: RefObject<HTMLElement | null>;
  online: boolean;
  install: InstallState;
  showInstall: () => void;
};

export const AppContext = createContext<AppCtx | null>(null);

export function useApp(): AppCtx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside AppContext");
  return ctx;
}
