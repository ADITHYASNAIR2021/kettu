"use client";

import { useEffect, useState } from "react";
import { lang } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Ear } from "./Icons";
import type { LangCode } from "@/lib/languages";

export type Phase = { kind: "upload" } | { kind: "job"; stage: string; position: number };

const ORDER = ["upload", "preparing", "transcribing", "understanding"] as const;

function current(phase: Phase): (typeof ORDER)[number] | "queued" {
  if (phase.kind === "upload") return "upload";
  if (phase.position > 0 || phase.stage === "queued") return "queued";
  if (phase.stage.startsWith("transcribing")) return "transcribing";
  if (phase.stage === "understanding" || phase.stage === "done") return "understanding";
  return "preparing";
}

export function Working({ phase, onCancel, targetLanguage, cancelDisabled = false }: { phase: Phase; onCancel: () => void; targetLanguage?: LangCode; cancelDisabled?: boolean }) {
  const { t, prefs } = useApp();
  // The free server sleeps when idle; the first upload then takes up to a minute. Say so instead of looking stuck.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (phase.kind !== "upload") return;
    const id = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(id);
  }, [phase.kind]);
  const now = current(phase);
  const nowIndex = now === "queued" ? 0.5 : ORDER.indexOf(now);
  const chunk = phase.kind === "job" && phase.stage.startsWith("transcribing") ? phase.stage.split(" ")[1] : null;

  const label: Record<(typeof ORDER)[number], string> = {
    upload: t("stage_upload"),
    preparing: t("stage_preparing"),
    transcribing: chunk && chunk !== "1/1" ? `${t("stage_transcribing")} · ${chunk}` : t("stage_transcribing"),
    understanding: t("stage_understanding", { lang: lang(targetLanguage ?? prefs.myLang)?.native ?? "" }),
  };

  return (
    <section className="stack reveal" style={{ gap: 18, alignItems: "stretch" }} aria-live="polite">
      <div className="rings" aria-hidden>
        <i /><i /><i />
        <div className="core"><Ear /></div>
      </div>
      {slow && phase.kind === "upload" && (
        <div className="alert calm" style={{ justifyContent: "center" }}>{t("waking_up")}</div>
      )}
      {now === "queued" && phase.kind === "job" && (
        <div className="alert calm" style={{ justifyContent: "center" }}>
          {t("stage_queued", { n: Math.max(1, phase.position - 1) })}
        </div>
      )}
      <ul className="stage-list card">
        {ORDER.map((s, i) => (
          <li key={s} data-state={i < nowIndex ? "done" : i === nowIndex ? "active" : "todo"}>{label[s]}</li>
        ))}
      </ul>
      <p className="small" style={{ margin: 0 }}>{t("processing_background")}</p>
      <button className="btn btn-ghost btn-block" disabled={cancelDisabled} onClick={onCancel}>{t("back")}</button>
    </section>
  );
}
