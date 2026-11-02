"use client";

import { useState } from "react";
import { UI_LANGS } from "@/lib/i18n";
import { LANGUAGES, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Close } from "./Icons";
import { useDialog } from "./useDialog";

export function SettingsSheet({ onClose }: { onClose: () => void }) {
  const { t, prefs, setPrefs } = useApp();
  const dialog = useDialog(onClose);
  const [word, setWord] = useState("");

  const addWord = () => {
    const w = word.trim().slice(0, 60);
    if (!w || prefs.keyterms.includes(w) || prefs.keyterms.length >= 50) return;
    setPrefs({ keyterms: [...prefs.keyterms, w] });
    setWord("");
  };

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div ref={dialog} tabIndex={-1} className="sheet" role="dialog" aria-modal="true" aria-label={t("settings")}>
        <div className="sheet-inner">
          <div className="grab" />
          <div className="row">
            <h2 className="title">{t("settings")}</h2>
            <span className="spacer" />
            <button className="icon-btn" onClick={onClose} aria-label={t("done")}><Close /></button>
          </div>

          <label className="stack" style={{ gap: 6 }}>
            <span className="eyebrow">{t("my_language")}</span>
            <select className="input" value={prefs.myLang ?? ""}
                    onChange={(e) => setPrefs({ myLang: e.target.value as LangCode })}>
              {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.native} · {l.name}</option>)}
            </select>
          </label>

          <div className="stack" style={{ gap: 6 }}>
            <span className="eyebrow">{t("app_language")}</span>
            <div className="seg" role="group">
              {UI_LANGS.map((u) => (
                <button key={u.code} aria-pressed={prefs.uiLang === u.code} onClick={() => setPrefs({ uiLang: u.code })}
                        lang={u.code}>
                  {u.label}
                </button>
              ))}
            </div>
          </div>

          <div className="stack" style={{ gap: 6 }}>
            <span className="eyebrow">{t("voice")}</span>
            <div className="seg" role="group">
              <button aria-pressed={prefs.voice === "female"} onClick={() => setPrefs({ voice: "female" })}>{t("voice_female")}</button>
              <button aria-pressed={prefs.voice === "male"} onClick={() => setPrefs({ voice: "male" })}>{t("voice_male")}</button>
            </div>
          </div>

          <div className="stack" style={{ gap: 8 }}>
            <span className="eyebrow">{t("my_words")} · {prefs.keyterms.length}/50</span>
            <span className="small">{t("my_words_hint")}</span>
            <form className="row" style={{ flexWrap: "nowrap" }} onSubmit={(e) => { e.preventDefault(); addWord(); }}>
              <input className="input" value={word} onChange={(e) => setWord(e.target.value)} placeholder="Rakib, M-sand, Kottayam…" />
              <button className="btn btn-ghost" type="submit" disabled={!word.trim()}>{t("add")}</button>
            </form>
            {prefs.keyterms.length > 0 && (
              <div className="tags">
                {prefs.keyterms.map((k) => (
                  <span className="tag" key={k}>
                    {k}
                    <button aria-label={`Remove ${k}`} onClick={() => setPrefs({ keyterms: prefs.keyterms.filter((x) => x !== k) })}>
                      <Close size={14} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <details className="card orig">
            <summary><span className="eyebrow">{t("privacy")}</span></summary>
            <p style={{ marginBottom: 0 }}>{t("consent_body")}</p>
            <a href="/privacy" target="_blank" rel="noopener noreferrer">{t("privacy")}</a>
          </details>

          <button className="btn btn-primary btn-block" onClick={onClose}>{t("done")}</button>
        </div>
      </div>
    </>
  );
}
