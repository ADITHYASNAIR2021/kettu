"use client";
import { useApp } from "./AppContext";

/** A short decorative transition; the result text itself is never delayed or streamed falsely. */
export function ReadyReveal() {
  const { t } = useApp();
  return <div className="ready-reveal" role="status"><span className="ready-wave" aria-hidden>
    {[12, 22, 32, 18, 28, 14].map((height, i) => <i key={i} style={{ height, animationDelay: `${i * 35}ms` }} />)}
  </span><span className="ready-caption">{t("ready_to_check")}</span></div>;
}
