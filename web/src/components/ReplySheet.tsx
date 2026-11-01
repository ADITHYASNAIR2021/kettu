"use client";

import { useEffect, useState } from "react";
import { ApiError, previewReply, speakReply, type ReplyDraft, type Voice } from "@/lib/api";
import { errorText } from "@/lib/i18n";
import { htmlLang, lang, LANGUAGES, type LangCode } from "@/lib/languages";
import { download, shareAudio } from "@/lib/share";
import { useApp } from "./AppContext";
import { Close, Download, Mic, Share, Speaker, Stop } from "./Icons";
import { useObjectUrl } from "./useObjectUrl";
import { mmss, useRecorder } from "./useRecorder";

type Props = {
  from: LangCode;
  to: LangCode;
  onClose: () => void;
  repliesLeft: number | null;
  onSpent: () => void;
  /** A new voice note of your own (not an answer to one), optionally starting from words you already have. */
  compose?: boolean;
  initialText?: string;
};

export const MAX_REPLY_CHARS = 700;

export function ReplySheet({ from, to: initialTo, onClose, repliesLeft, onSpent, compose, initialText }: Props) {
  const { t, prefs, setPrefs, device } = useApp();
  const [to, setTo] = useState<LangCode>(initialTo);
  const [text, setText] = useState((initialText ?? "").slice(0, MAX_REPLY_CHARS));
  const [draft, setDraft] = useState<ReplyDraft | null>(null);
  const [audio, setAudio] = useState<Blob | null>(null);
  const audioUrl = useObjectUrl(audio);
  const [busy, setBusy] = useState<"translate" | "speak" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fail = (e: unknown) => setError(e instanceof ApiError ? errorText(t, e.code, e.message) : t("err_offline"));

  const translate = async (opts: { text?: string; audio?: Blob }) => {
    setError(null);
    setBusy("translate");
    try {
      const d = await previewReply({ fromLang: from, toLang: to, deviceId: device, ...opts });
      setDraft(d);
      setText(d.source_text);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const rec = useRecorder((blob) => translate({ audio: blob }));

  const speak = async () => {
    if (!draft) return;
    setError(null);
    setBusy("speak");
    try {
      setAudio(await speakReply({ targetText: draft.target_text, toLang: to, voice: prefs.voice, deviceId: device }));
      onSpent();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const theirs = lang(to);
  const mine = lang(from);
  const filename = `kettu-reply-${theirs?.name.toLowerCase() ?? "audio"}.mp3`;

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet" role="dialog" aria-modal="true" aria-label={compose ? t("compose_title") : t("reply_title")}>
        <div className="sheet-inner">
          <div className="grab" />
          <div className="row">
            <h2 className="title">{compose ? t("compose_title") : t("reply_title")}</h2>
            <span className="spacer" />
            <button className="icon-btn" onClick={onClose} aria-label={t("cancel")}><Close /></button>
          </div>
          {compose && !draft && (
            <p className="small" style={{ margin: 0 }}>{t("compose_hint", { lang: mine?.native ?? "" })}</p>
          )}

          {!draft && (
            <>
              <label className="stack" style={{ gap: 6 }}>
                <span className="eyebrow">{t("reply_to")}</span>
                <select className="input" value={to} onChange={(e) => setTo(e.target.value as LangCode)}>
                  {LANGUAGES.filter((l) => l.code !== from).map((l) => (
                    <option key={l.code} value={l.code}>{l.native} · {l.name}</option>
                  ))}
                </select>
              </label>

              <p style={{ margin: 0, fontWeight: 600 }}>{t("type_or_speak", { lang: mine?.native ?? "" })}</p>

              <div className="card rec" style={{ padding: 14 }}>
                <button className="rec-btn" data-on={rec.recording} onClick={rec.toggle} disabled={busy !== null}
                        aria-label={rec.recording ? t("stop") : t("speak")}>
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
                  <strong>{busy === "translate" ? "…" : t("speak")}</strong>
                )}
              </div>

              <textarea
                className="input"
                rows={3}
                maxLength={MAX_REPLY_CHARS}
                lang={htmlLang(from)}
                placeholder={t("placeholder")}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <button className="btn btn-primary btn-block" disabled={!text.trim() || busy !== null}
                      onClick={() => translate({ text })}>
                {busy === "translate" ? "…" : t("translate")}
              </button>
            </>
          )}

          {draft && !audio && (
            <>
              <div className="draft target">
                <span className="eyebrow">{t("they_hear")} · {theirs?.native}</span>
                <p lang={htmlLang(to)}>{draft.target_text}</p>
              </div>
              <div className="draft back">
                <span className="eyebrow">{t("meaning", { lang: mine?.native ?? "" })}</span>
                <p lang={htmlLang(from)}>{draft.back_translation}</p>
              </div>
              <div className="seg" role="group" aria-label={t("voice")}>
                {(["female", "male"] as Voice[]).map((v) => (
                  <button key={v} aria-pressed={prefs.voice === v} onClick={() => setPrefs({ voice: v })}>
                    {v === "female" ? t("voice_female") : t("voice_male")}
                  </button>
                ))}
              </div>
              <button className="btn btn-leaf btn-block" onClick={speak} disabled={busy !== null}>
                <Speaker /> {busy === "speak" ? t("making_voice") : t("make_voice")}
              </button>
              <button className="btn btn-ghost btn-block" onClick={() => setDraft(null)} disabled={busy !== null}>
                {t("change")}
              </button>
              {repliesLeft !== null && <p className="small" style={{ margin: 0, textAlign: "center" }}>{t("replies_left", { n: repliesLeft })}</p>}
            </>
          )}

          {audio && audioUrl && draft && (
            <>
              <div className="draft target">
                <span className="eyebrow">{theirs?.native}</span>
                <p lang={htmlLang(to)}>{draft.target_text}</p>
              </div>
              <audio controls autoPlay src={audioUrl} />
              <button className="btn btn-primary btn-block"
                      onClick={() => shareAudio(audio, filename, t("share_caption", { lang: theirs?.name ?? "" }))}>
                <Share /> {t("share_whatsapp")}
              </button>
              <button className="btn btn-ghost btn-block" onClick={() => download(audio, filename)}>
                <Download /> {t("save_audio")}
              </button>
              <p className="small" style={{ margin: 0 }}>{t("ai_voice")}</p>
            </>
          )}

          {error && <div className="alert" role="alert">{error}</div>}
        </div>
      </div>
    </>
  );
}
