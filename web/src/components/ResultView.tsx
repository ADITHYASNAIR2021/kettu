"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  ApiError, reviewNote, sendFeedback, speakReply, translateText, type Entity, type NoteResult, type TextTranslation,
} from "@/lib/api";
import { errorText } from "@/lib/i18n";
import { htmlLang, lang, LANGUAGES, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Copy, Reply, Speaker, Stop } from "./Icons";
import { useObjectUrl } from "./useObjectUrl";
import { mmss } from "./useRecorder";
import { CardWorkspace } from "./CardWorkspace";
import type { ReplySeed } from "@/lib/cards";
import { TranscriptEditor } from "./TranscriptEditor";
import { CLARIFICATIONS, type Clarification } from "@/lib/clarifications";

type Segment = { text: string; entity: number | null };

/** Splits the transcript so each entity's exact source words can be highlighted when its chip is tapped. */
function segments(text: string, entities: Entity[]): Segment[] {
  const hits: { start: number; end: number; entity: number }[] = [];
  entities.forEach((e, i) => {
    if (!e.source_text) return;
    let from = 0;
    for (;;) {
      const at = text.indexOf(e.source_text, from);
      if (at < 0) break;
      const end = at + e.source_text.length;
      if (!hits.some((h) => at < h.end && end > h.start)) {
        hits.push({ start: at, end, entity: i });
        break;
      }
      from = at + 1;
    }
  });
  hits.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let pos = 0;
  for (const h of hits) {
    if (h.start > pos) out.push({ text: text.slice(pos, h.start), entity: null });
    out.push({ text: text.slice(h.start, h.end), entity: h.entity });
    pos = h.end;
  }
  if (pos < text.length) out.push({ text: text.slice(pos), entity: null });
  return out;
}

const ENTITY_ICON: Record<Entity["type"], string> = {
  time: "🕗", date: "📅", amount: "₹", quantity: "#", name: "👤", place: "📍",
};

/** FR14: hear the translation in your own language, for people who prefer listening to reading. */
function ReadAloud({ text, lang: code }: { text: string; lang: LangCode }) {
  const { t, prefs, device, online } = useApp();
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const player = useRef<HTMLAudioElement | null>(null);
  const objectUrl = useRef<string | null>(null);
  const generation = useRef(0);

  useEffect(() => () => {
    generation.current += 1;
    player.current?.pause();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
  }, []);

  if (!text) return null;

  const toggle = async () => {
    if (state === "playing") {
      player.current?.pause();
      setState("idle");
      return;
    }
    setState("loading");
    const current = generation.current;
    try {
      if (player.current) {
        await player.current.play();
        if (current === generation.current) setState("playing");
        return;
      }
      const blob = await speakReply({ targetText: text, toLang: code, voice: prefs.voice, deviceId: device, purpose: "read_aloud" });
      if (current !== generation.current) return;
      const url = URL.createObjectURL(blob);
      objectUrl.current = url;
      const audio = new Audio(url);
      player.current = audio;
      audio.onended = () => setState("idle");
      await audio.play();
      if (current === generation.current) setState("playing");
    } catch {
      if (current === generation.current) setState("error");
    }
  };

  return (
    <button className="btn btn-ghost btn-sm" onClick={toggle} disabled={state === "loading" || !online} aria-live="polite"
            title={state === "error" ? t("err_busy") : undefined}>
      {state === "playing" ? <Stop size={18} /> : <Speaker size={18} />}
      {state === "loading" ? "…" : state === "playing" ? t("stop_listening") : t("listen")}
    </button>
  );
}

/** Amounts, times, counts or names the server found in the note but not in the translation. */
function MissingFacts({ facts }: { facts: string[] }) {
  const { t } = useApp();
  if (!facts.length) return null;
  return (
    <div className="alert" role="status">
      <span>⚠ {t("missing_facts")} <strong>{facts.join(" · ")}</strong></span>
    </div>
  );
}

/** Read the same note in any of the ten languages, not only your own. */
function OtherLanguage({ result }: { result: NoteResult }) {
  const { t, device, online } = useApp();
  const [to, setTo] = useState<LangCode | "">("");
  const [out, setOut] = useState<TextTranslation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef<string>("");

  const pick = async (code: LangCode | "") => {
    latest.current = code;
    setTo(code);
    setOut(null);
    setError(null);
    if (!code) return;
    setBusy(true);
    try {
      const res = await translateText({ text: result.transcript, fromLang: result.detected_lang, toLang: code, deviceId: device });
      if (latest.current === code) setOut(res);
    } catch (e) {
      if (latest.current === code) setError(e instanceof ApiError ? errorText(t, e.code, e.message) : t("err_offline"));
    } finally {
      if (latest.current === code) setBusy(false);
    }
  };

  const choices = LANGUAGES.filter((l) => l.code !== result.my_lang && l.code !== result.detected_lang);

  return (
    <div className="card stack">
      <label className="stack" style={{ gap: 6 }}>
        <span className="eyebrow">{t("read_in")}</span>
        <select className="input" value={to} disabled={!online} onChange={(e) => pick(e.target.value as LangCode | "")}>
          <option value="">{t("choose_lang")}</option>
          {choices.map((l) => (
            <option key={l.code} value={l.code}>{l.native} · {l.name}</option>
          ))}
        </select>
      </label>
      {busy && <p className="small" style={{ margin: 0 }}>…</p>}
      {out && !out.translation_live && <div className="alert calm">{t("translation_off")}</div>}
      {out && out.translation_live && to && (
        <>
          <div className="row">
            <p className="eyebrow">{t("in_lang", { lang: lang(to)?.native ?? "" })}</p>
            <span className="spacer" />
            <ReadAloud key={`${to}:${out.translation}`} text={out.translation.length <= 900 ? out.translation : ""} lang={to} />
          </div>
          <p className="translation" lang={htmlLang(to)}>{out.translation}</p>
          <MissingFacts facts={out.missing_facts} />
        </>
      )}
      {error && <div className="alert" role="alert">{error}</div>}
    </div>
  );
}

type Props = { result: NoteResult; audio: Blob | null; onReply: (seed: ReplySeed) => void; onSendOther: () => void;
  onNew: () => void; onUpdate: (result: NoteResult) => void };

export function ResultView({ result, audio, onReply, onSendOther, onNew, onUpdate }: Props) {
  const { t, device, prefs, online } = useApp();
  const [active, setActive] = useState<number | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [reasonSent, setReasonSent] = useState(false);
  const audioUrl = useObjectUrl(audio);
  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const reviewRequest = useRef<AbortController | null>(null);
  useEffect(() => () => reviewRequest.current?.abort(), []);

  const src = lang(result.detected_lang);
  const mine = lang(result.my_lang);
  const segs = useMemo(() => segments(result.transcript, result.entities), [result]);
  const canReply = Boolean(result.detected_lang && !result.same_language);
  const live = result.translation_live !== false;

  const review = async (text: string, source: LangCode | null) => {
    if (reviewing) return;
    if (!online) return;
    const controller = new AbortController();
    reviewRequest.current = controller;
    setReviewing(true);
    setReviewError(null);
    try {
      const refreshed = await reviewNote({ text, sourceLang: source, myLang: result.my_lang,
        duration: result.duration_s, mode: result.order_items !== null ? "orders" : "listen",
        deviceId: device, signal: controller.signal });
      if (controller.signal.aborted) return;
      onUpdate({ ...result, ...refreshed,
        original_transcript: result.original_transcript ?? result.transcript,
        transcript_edited: refreshed.transcript !== (result.original_transcript ?? result.transcript),
        revision: (result.revision ?? 0) + 1,
      });
    } catch (error) {
      if (!controller.signal.aborted) setReviewError(error instanceof ApiError ? errorText(t, error.code, error.message) : t("err_offline"));
    } finally {
      if (!controller.signal.aborted) setReviewing(false);
    }
  };

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(key);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      /* clipboard blocked */
    }
  };

  const rate = (r: 1 | -1) => {
    setRating(r);
    if (r === 1) sendFeedback({ kind: "note", rating: 1, lang: result.my_lang, deviceId: device });
  };
  const reason = (why: string) => {
    sendFeedback({ kind: "note", rating: -1, reason: why, lang: result.my_lang, deviceId: device });
    setReasonSent(true);
  };

  // Timbre takes up to ~900 characters; for very long notes, read the gist instead.
  const readAloudText =
    result.translation && result.translation.length <= 900 ? result.translation : (result.gist ?? "");

  const orderText = result.order_items?.map((i) => `☐ ${i.item} — ${i.quantity} ${i.unit}`.trim()).join("\n") ?? "";

  return (
    <section className="stack reveal" style={{ gap: 14 }}>
      {result.speech_live === false && <div className="alert" role="status">{t("demo_mode")}</div>}
      <div className="row">
        <span className="badge" lang={htmlLang(result.detected_lang)}>
          {t("heard_in", { lang: src?.native ?? "?" })}
        </span>
        <span className="small">{mmss(result.duration_s)}</span>
      </div>

      {result.gist && (
        <div className="stack" style={{ gap: 6 }}>
          <p className="eyebrow">{t("gist")}</p>
          <div className="gist" lang={htmlLang(result.my_lang)}>{result.gist}</div>
          <p className="small" style={{ margin: 0 }}>{t("ai_summary")}</p>
        </div>
      )}

      {!live && !result.same_language ? (
        <div className="alert calm">{t("translation_off")}</div>
      ) : result.translation ? (
        <div className="card stack">
          <div className="row">
            <p className="eyebrow">{t("in_lang", { lang: mine?.native ?? "" })}</p>
            <span className="spacer" />
            <ReadAloud text={readAloudText} lang={result.my_lang} />
            <button className="btn btn-ghost btn-sm" onClick={() => copy("tr", result.translation!)}>
              <Copy /> {copied === "tr" ? t("copied") : t("copy")}
            </button>
          </div>
          <p className="translation" lang={htmlLang(result.my_lang)}>{result.translation}</p>
        </div>
      ) : (
        result.same_language && <div className="alert calm">✓ {t("already", { lang: mine?.native ?? "" })}</div>
      )}

      {live && <MissingFacts facts={result.missing_facts ?? []} />}

      {result.entities.length > 0 && (
        <div className="chips" role="group">
          {result.entities.map((e, i) => (
            <button
              key={i}
              className="chip"
              aria-pressed={active === i}
              onClick={() => setActive(active === i ? null : i)}
              lang={htmlLang(result.my_lang)}
            >
              <span aria-hidden>{ENTITY_ICON[e.type]}</span> {e.value}
            </button>
          ))}
        </div>
      )}

      {result.order_items && result.order_items.length > 0 && (
        <div className="card stack">
          <p className="small" style={{ margin: 0 }}>{t("ai_summary")}</p>
          <div className="row">
            <p className="eyebrow">🛒 {t("order_list")}</p>
            <span className="spacer" />
            <button className="btn btn-ghost btn-sm" onClick={() => copy("order", orderText)}>
              <Copy /> {copied === "order" ? t("copied") : t("copy")}
            </button>
          </div>
          <ul className="checklist" lang={htmlLang(result.my_lang)}>
            {result.order_items.map((it, i) => (
              <li key={i}>
                <label>
                  <input type="checkbox" />
                  <span>{it.item}</span>
                  <span className="qty">{it.quantity} {it.unit}</span>
                </label>
              </li>
            ))}
          </ul>
        </div>
      )}

      <details className="card orig" open={!result.translation || !live || active !== null}>
        <summary>
          <span className="eyebrow">{result.transcript_edited ? t("edited_words") : t("original")} · {src?.native}</span>
        </summary>
        <div className="stack" style={{ marginTop: 8 }}>
          <p className="transcript" lang={htmlLang(result.detected_lang)}>
            {segs.map((s, i) =>
              s.entity === null ? (
                <span key={i}>{s.text}</span>
              ) : (
                <mark key={i} data-on={active === s.entity}>{s.text}</mark>
              ),
            )}
          </p>
          {audioUrl && <audio controls src={audioUrl} preload="metadata" aria-label={t("play_original")} />}
          {!audioUrl && <p className="small">{t("audio_unavailable")}</p>}
          {result.transcript_edited && result.original_transcript && <details>
            <summary>{t("original_recognition")}</summary>
            <p className="transcript" lang={htmlLang(result.detected_lang)}>{result.original_transcript}</p>
          </details>}
        </div>
      </details>

      <TranscriptEditor result={result} busy={reviewing} onReview={review} />
      {reviewError && <div className="alert" role="alert">{reviewError}</div>}

      <CardWorkspace items={result.action_items ?? []} reviewed={result.actions_reviewed === true || Boolean(result.action_items?.length)}
        busy={reviewing} available={live} language={result.my_lang} sourceLanguage={result.detected_lang}
        onReply={onReply}
        onExtract={() => review(result.transcript, result.detected_lang)} />

      <OtherLanguage result={result} />

      {result.detected_lang && prefs.myLang && live && <section className="card stack" aria-label={t("clarify_title")}>
        <h2 className="title">{t("clarify_title")}</h2>
        <p className="small" style={{ margin: 0 }}>{t("clarify_hint")}</p>
        {(["date", "quantity", "repeat"] as Clarification[]).map((kind) => <button key={kind}
          className="btn btn-ghost btn-block" disabled={reviewing || !online}
          onClick={() => onReply({ text: CLARIFICATIONS[prefs.myLang!][kind], from: prefs.myLang!, to: result.detected_lang! })}>{t(`clarify_${kind}`)}</button>)}
      </section>}

      {canReply && (
        <button className="btn btn-primary btn-block" disabled={!online} onClick={() => prefs.myLang && result.detected_lang && onReply({ text: "", from: prefs.myLang, to: result.detected_lang })}>
          <Reply /> {t("reply_in", { lang: src?.native ?? "" })}
        </button>
      )}
      <button className={`btn btn-block ${canReply ? "btn-ghost" : "btn-primary"}`} disabled={!online} onClick={onSendOther}>
        <Speaker /> {t("send_other")}
      </button>

      <div className="card stack" style={{ padding: 16 }}>
        <div className="feedback">
          <span style={{ fontWeight: 600 }}>{t("was_right")}</span>
          <span className="spacer" />
          <button className="thumb" aria-pressed={rating === 1} onClick={() => rate(1)} aria-label="Yes">👍</button>
          <button className="thumb" aria-pressed={rating === -1} onClick={() => rate(-1)} aria-label="No">👎</button>
        </div>
        {rating === -1 && !reasonSent && (
          <div className="row">
            {(["wrong_language", "wrong_words", "bad_translation"] as const).map((r) => (
              <button key={r} className="btn btn-ghost btn-sm" onClick={() => reason(r)}>{t(r)}</button>
            ))}
          </div>
        )}
        {(rating === 1 || reasonSent) && <span className="small">{t("thanks")}</span>}
      </div>

      <button className="btn btn-ghost btn-block" onClick={onNew}>{t("another")}</button>
    </section>
  );
}
