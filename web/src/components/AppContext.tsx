"use client";

import { createContext, useContext } from "react";
import type { T } from "@/lib/i18n";
import type { Prefs } from "@/lib/prefs";

export type AppCtx = {
  t: T;
  prefs: Prefs;
  setPrefs: (p: Partial<Prefs>) => void;
  device: string;
};

export const AppContext = createContext<AppCtx | null>(null);

export function useApp(): AppCtx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp outside AppContext");
  return ctx;
}
