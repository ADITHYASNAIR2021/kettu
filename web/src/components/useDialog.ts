"use client";

import { useEffect, useRef } from "react";
import { useApp } from "./AppContext";

const FOCUSABLE = 'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]';

/** Move keyboard focus into a sheet, contain it there, then restore it on close. */
export function useDialog(onClose: () => void) {
  const { dialogTrigger } = useApp();
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);
  useEffect(() => {
    const previous = dialogTrigger.current;
    const dialog = ref.current;
    if (!dialog) return;
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.getClientRects().length > 0);
    (controls()[0] ?? dialog).focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close.current();
      }
      if (event.key !== "Tab") return;
      const items = controls();
      const first = items[0];
      const last = items[items.length - 1];
      if (!first) { event.preventDefault(); dialog.focus(); return; }
      if (event.shiftKey && (document.activeElement === first || !dialog.contains(document.activeElement))) {
        event.preventDefault(); last.focus();
      } else if (!event.shiftKey && (document.activeElement === last || !dialog.contains(document.activeElement))) {
        event.preventDefault(); first.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      // Wait until React has removed `inert` from the page behind the sheet.
      requestAnimationFrame(() => { if (previous?.isConnected) previous.focus(); });
    };
  }, [dialogTrigger]);
  return ref;
}
