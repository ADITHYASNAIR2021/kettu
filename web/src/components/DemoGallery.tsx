"use client";
import { useEffect, useRef, useState } from "react";
import { DEMOS } from "@/lib/demos";
import { lang } from "@/lib/languages";
import { useApp } from "./AppContext";

export function DemoGallery({ previous, onBack, onAudio }: { previous?: string | null; onBack: () => void;
  onAudio: (blob: Blob, filename: string, id: string) => void }) {
  const { t, online } = useApp();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const request = useRef<AbortController | null>(null);
  useEffect(() => () => request.current?.abort(), []);
  const choose = async (demo: typeof DEMOS[number]) => {
    if (loading || !online) return;
    const ctl = new AbortController(); request.current = ctl;
    setLoading(demo.id); setError(false);
    try {
      const response = await fetch(demo.path, { signal: ctl.signal });
      if (!response.ok) throw new Error("Sample unavailable");
      const blob = await response.blob();
      if (!ctl.signal.aborted) onAudio(blob, demo.path.split("/").pop()!, demo.id);
    } catch { if (!ctl.signal.aborted) setError(true); }
    finally { if (!ctl.signal.aborted) setLoading(null); }
  };
  return <section className="stack reveal">
    <h1 className="display">{t("pick_scenario")}</h1><p className="lede">{t("demo_intro")}</p>
    {DEMOS.map((demo, i) => <article className="card stack demo-scenario" key={demo.id}>
      <span className="eyebrow">0{i + 1} · {lang(demo.language)?.native}</span><h2 className="title">{t(demo.title)}</h2>
      <p>{t(demo.hint)}</p>{previous === demo.id && <span className="small">{t("last_scenario")}</span>}
      <audio controls preload="none" src={demo.path} aria-label={t(demo.title)} />
      <button className="btn btn-leaf btn-block" disabled={!online || loading !== null} onClick={() => choose(demo)}>
        {loading === demo.id ? "…" : t("try_scenario")}</button>
    </article>)}
    {error && <div className="alert" role="alert">{t("sample_unavailable")}</div>}
    <p className="small">{t("demo_usage")}</p>
    <button className="btn btn-ghost btn-block" onClick={onBack}>{t("back")}</button>
  </section>;
}
