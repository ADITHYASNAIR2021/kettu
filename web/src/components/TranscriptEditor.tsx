"use client";

import { useState } from "react";
import type { NoteResult } from "@/lib/api";
import { htmlLang, LANGUAGES, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";

type Props = {
  result: NoteResult;
  busy: boolean;
  onReview: (text: string, source: LangCode | null) => void;
};

export function TranscriptEditor({ result, busy, onReview }: Props) {
  const { t, online } = useApp();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(result.transcript);
  const [source, setSource] = useState<LangCode | "">(result.detected_lang ?? "");
  const changed = text.trim() !== result.transcript || source !== (result.detected_lang ?? "");

  if (!editing) return (
    <div className="stack" style={{ gap: 8 }}>
      <button className="btn btn-ghost btn-block" onClick={() => setEditing(true)} disabled={busy}>
        {t("edit_transcript")}
      </button>
      {result.transcript_edited && <p className="small" style={{ margin: 0 }}>{t("transcript_edited")}</p>}
    </div>
  );

  return (
    <form className="card stack transcript-editor" onSubmit={(event) => { event.preventDefault(); onReview(text, source || null); }}>
      <h2 className="title">{t("edit_transcript")}</h2>
      <p className="small" style={{ margin: 0 }}>{t("edit_transcript_hint")}</p>
      <label className="stack" style={{ gap: 6 }}>
        <span className="eyebrow">{t("spoken_language")}</span>
        <select className="input" value={source} onChange={(event) => setSource(event.target.value as LangCode | "")} disabled={busy}>
          <option value="">{t("language_unknown")}</option>
          {LANGUAGES.map((language) => <option key={language.code} value={language.code}>{language.native} · {language.name}</option>)}
        </select>
      </label>
      <label className="stack" style={{ gap: 6 }}>
        <span className="eyebrow">{t("transcript_words")}</span>
        <textarea className="input" rows={7} value={text} maxLength={6000} lang={htmlLang(source)}
          disabled={busy} onChange={(event) => setText(event.target.value)} />
      </label>
      <span className="small">{text.length}/6000</span>
      {result.original_transcript && text !== result.original_transcript && (
        <button type="button" className="btn btn-ghost btn-sm" disabled={busy}
          onClick={() => setText(result.original_transcript!)}>{t("use_original_words")}</button>
      )}
      <button className="btn btn-primary btn-block" type="submit" disabled={!online || busy || !changed || !text.trim() || text.length > 6000}>
        {busy ? t("updating_note") : t("update_translation")}
      </button>
      <button className="btn btn-ghost btn-block" type="button" disabled={busy} onClick={() => setEditing(false)}>{t("cancel")}</button>
    </form>
  );
}
