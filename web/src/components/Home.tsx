"use client";

import { useRef } from "react";
import type { Limits } from "@/lib/api";
import { lang } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Mic, Stop, Upload } from "./Icons";

import { mmss, useRecorder } from "./useRecorder";

type Props = {
  onAudio: (blob: Blob, filename: string) => void;
  orders: boolean;
  setOrders: (v: boolean) => void;
  limits: Limits | null;
  notice: string | null;
  onCompose: () => void;
  onSaved: () => void;
  onDemo: () => void;
  onConversation: () => void;
  noteBlocked: boolean;
};

export function Home({ onAudio, orders, setOrders, limits, notice, onCompose, onSaved, onDemo, onConversation, noteBlocked }: Props) {
  const { t, prefs, online } = useApp();
  const file = useRef<HTMLInputElement>(null);
  const rec = useRecorder((blob) => onAudio(blob, `recording${blob.type.includes("mp4") ? ".m4a" : ".webm"}`));
  const mine = lang(prefs.myLang);

  return (
    <section className="stack home-view">
      <div className="stack" style={{ gap: 6 }}>
        <p className="eyebrow">{mine?.native}</p>
        <h1 className="display">{t("home_title")}</h1>
        <p className="lede">{t("home_hint")}</p>
      </div>

      {notice && <div className="alert" role="status">{notice}</div>}
      {limits?.speech_live === false && <div className="alert" role="status">{t("demo_mode")}</div>}
      {limits && !limits.service_open && (
        <div className="alert"><strong>{t("waitlist_title")}.</strong> {t("err_service_budget")}</div>
      )}

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
        <button className="btn btn-primary btn-block" disabled={!online || noteBlocked || rec.recording || rec.starting} onClick={() => file.current?.click()}>
          <Upload /> {t("upload")}
        </button>

        <div className="rec home-rec">
          <button
            className="rec-btn"
            data-on={rec.recording}
            onClick={rec.toggle}
            disabled={rec.starting || (!rec.recording && (!online || noteBlocked))}
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

        <label className="toggle home-order">
          <input type="checkbox" checked={orders} onChange={(e) => setOrders(e.target.checked)} />
          <span className="track" />
          <span className="stack" style={{ gap: 0 }}>
            <strong>{t("orders_mode")}</strong>
            <span className="small">{t("orders_hint")}</span>
          </span>
        </label>
      </div>

      <nav className="home-links" aria-label={t("more_options")}>
        <button className="home-link" disabled={!online || noteBlocked || rec.recording || rec.starting} onClick={onConversation}>
          <span>{t("conversation_mode")}</span><span aria-hidden>→</span>
        </button>
        <button className="home-link" onClick={onCompose} disabled={!online || rec.recording || rec.starting}>
          <span>{t("compose")}</span><span aria-hidden>→</span>
        </button>
        <button className="home-link" onClick={onSaved}><span>{t("saved_cards")}</span><span aria-hidden>→</span></button>
        <button className="home-link" onClick={onDemo} disabled={!online || noteBlocked || rec.recording || rec.starting}>
          <span>{t("sample_link")}</span><span aria-hidden>→</span>
        </button>
      </nav>

      {limits && <p className="small" style={{ margin: 0 }}>{t("left_today", { n: limits.notes_left })}</p>}
    </section>
  );
}
