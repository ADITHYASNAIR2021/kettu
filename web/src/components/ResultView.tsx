"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { sendFeedback, speakReply, type Entity, type NoteResult } from "@/lib/api";
import { htmlLang, lang, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Copy, Reply, Speaker, Stop } from "./Icons";
import { useObjectUrl } from "./useObjectUrl";
import { mmss } from "./useRecorder";

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
  const { t, prefs, device } = useApp();
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const player = useRef<HTMLAudioElement | null>(null);

  useEffect(() => () => player.current?.pause(), []);

  if (!text) return null;

  const toggle = async () => {
    if (state === "playing") {
      player.current?.pause();
      setState("idle");
      return;
    }
    setState("loading");
    try {
      const blob = await speakReply({ targetText: text, toLang: code, voice: prefs.voice, deviceId: device, purpose: "read_aloud" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      player.current = audio;
      audio.onended = () => { setState("idle"); URL.revokeObjectURL(url); };
      await audio.play();
      setState("playing");
    } catch {
      setState("error");
    }
  };

  return (
    <button className="btn btn-ghost btn-sm" onClick={toggle} disabled={state === "loading"} aria-live="polite"
            title={state === "error" ? t("err_busy") : undefined}>
      {state === "playing" ? <Stop size={18} /> : <Speaker size={18} />}
      {state === "loading" ? "…" : state === "playing" ? t("stop_listening") : t("listen")}
    </button>
  );
}

type Props = { result: NoteResult; audio: Blob | null; onReply: () => void; onNew: () => void };

export function ResultView({ result, audio, onReply, onNew }: Props) {
  const { t, device } = useApp();
  const [active, setActive] = useState<number | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [rating, setRating] = useState<1 | -1 | null>(null);
  const [reasonSent, setReasonSent] = useState(false);
  const audioUrl = useObjectUrl(audio);

  const src = lang(result.detected_lang);
  const mine = lang(result.my_lang);
  const segs = useMemo(() => segments(result.transcript, result.entities), [result]);
  const canReply = Boolean(result.detected_lang && !result.same_language);

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

      {result.translation ? (
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

      <details className="card orig" open={!result.translation || active !== null}>
        <summary>
          <span className="eyebrow">{t("original")} · {src?.native}</span>
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
        </div>
      </details>

      {canReply && (
        <button className="btn btn-primary btn-block" onClick={onReply}>
          <Reply /> {t("reply_in", { lang: src?.native ?? "" })}
        </button>
      )}

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
