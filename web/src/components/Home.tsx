"use client";

import { useRef, useState } from "react";
import type { Limits } from "@/lib/api";
import { lang } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Mic, Play, Stop, Upload } from "./Icons";

// Synthetic note (Gnani Timbre voice, fake names and amounts) so visitors can try Kettu without one of their own.
const SAMPLE_URL = "/samples/site-worker-bengali.ogg";
import { mmss, useRecorder } from "./useRecorder";
import { useInstall } from "./useInstall";

type Props = {
  onAudio: (blob: Blob, filename: string) => void;
  orders: boolean;
  setOrders: (v: boolean) => void;
  limits: Limits | null;
  notice: string | null;
};

export function Home({ onAudio, orders, setOrders, limits, notice }: Props) {
  const { t, prefs } = useApp();
  const file = useRef<HTMLInputElement>(null);
  const { canInstall, installed, platform, install } = useInstall();
  const rec = useRecorder((blob) => onAudio(blob, `recording${blob.type.includes("mp4") ? ".m4a" : ".webm"}`));
  const mine = lang(prefs.myLang);
  const [loadingSample, setLoadingSample] = useState(false);

  const trySample = async () => {
    setLoadingSample(true);
    try {
      const resp = await fetch(SAMPLE_URL);
      if (resp.ok) onAudio(await resp.blob(), "site-worker-bengali.ogg");
    } finally {
      setLoadingSample(false);
    }
  };

  return (
    <section className="stack reveal" style={{ gap: 16 }}>
      <div className="stack" style={{ gap: 6 }}>
        <p className="eyebrow">{mine?.native}</p>
        <h1 className="display" style={{ fontSize: "clamp(32px, 8.5vw, 42px)" }}>{t("tagline")}</h1>
      </div>

      {notice && <div className="alert" role="status">{notice}</div>}
      {limits && !limits.service_open && (
        <div className="alert"><strong>{t("waitlist_title")}.</strong> {t("err_service_budget")}</div>
      )}

      <div className="card stack">
        <p className="eyebrow">{t("how_title")}</p>
        <ol className="steps" style={{ margin: 0, padding: 0, listStyle: "none" }}>
          <li className="step">{t("how_1")}</li>
          <li className="step">{t("how_2")}</li>
          <li className="step">{t("how_3")}</li>
        </ol>
        {!installed && platform !== "desktop" && (
          <div className="alert calm" style={{ flexDirection: "column", gap: 10 }}>
            <strong>{t("install_title")}</strong>
            <span>{platform === "ios" ? t("install_ios") : t("install_body")}</span>
            {canInstall && (
              <button className="btn btn-leaf btn-sm" onClick={install}>{t("install_btn")}</button>
            )}
          </div>
        )}
      </div>

      <div className="divider">{t("or")}</div>

      <div className="stack">
        <input
          ref={file}
          type="file"
          accept="audio/*,.opus,.ogg,.m4a,.mp3,.wav,.aac,.amr"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onAudio(f, f.name);
            e.target.value = "";
          }}
        />
        <button className="btn btn-primary btn-block" onClick={() => file.current?.click()}>
          <Upload /> {t("upload")}
        </button>

        <button className="btn btn-ghost btn-block sample-btn" onClick={trySample} disabled={loadingSample}>
          <Play /> {t("try_sample")}
        </button>
        <p className="small" style={{ margin: "-4px 4px 0" }}>{t("sample_hint")}</p>

        <div className="card rec" style={{ padding: 14 }}>
          <button
            className="rec-btn"
            data-on={rec.recording}
            onClick={rec.toggle}
            aria-label={rec.recording ? t("stop") : t("record")}
          >
            {rec.recording ? <Stop size={28} /> : <Mic size={30} />}
          </button>
          {rec.recording ? (
            <>
              <div className="bars" aria-hidden>
                {rec.levels.map((l, i) => <span key={i} style={{ height: `${Math.round(l * 40)}px` }} />)}
              </div>
              <span className="timer">{mmss(rec.seconds)}</span>
            </>
          ) : (
            <div className="stack" style={{ gap: 0 }}>
              <strong>{t("record")}</strong>
              <span className="small">{rec.error ? t("err_mic") : "≤ 3:00"}</span>
            </div>
          )}
        </div>

        <label className="toggle card" style={{ padding: "6px 16px" }}>
          <input type="checkbox" checked={orders} onChange={(e) => setOrders(e.target.checked)} />
          <span className="track" />
          <span className="stack" style={{ gap: 0 }}>
            <strong>🛒 {t("orders_mode")}</strong>
            <span className="small">{t("orders_hint")}</span>
          </span>
        </label>
      </div>

      {limits && <p className="small" style={{ textAlign: "center", margin: 0 }}>{t("left_today", { n: limits.notes_left })}</p>}
    </section>
  );
}
