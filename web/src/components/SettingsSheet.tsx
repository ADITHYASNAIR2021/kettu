"use client";

import { UI_LANGS } from "@/lib/i18n";
import { LANGUAGES, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Close } from "./Icons";
import { useDialog } from "./useDialog";
import { InstallButton } from "./Install";
import { feedbackSound } from "@/lib/sounds";

export function SettingsSheet({ onClose }: { onClose: () => void }) {
  const { t, prefs, setPrefs } = useApp();
  const dialog = useDialog(onClose);
  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div ref={dialog} tabIndex={-1} className="sheet" role="dialog" aria-modal="true" aria-label={t("settings")}>
        <div className="sheet-inner settings-content">
          <div className="grab" />
          <div className="row">
            <h2 className="title">{t("settings")}</h2>
            <span className="spacer" />
            <button className="icon-btn" onClick={onClose} aria-label={t("done")}><Close /></button>
          </div>

          <InstallButton />

          <label className="toggle settings-sound">
            <input type="checkbox" checked={prefs.sounds} onChange={(event) => {
              const enabled = event.target.checked; setPrefs({ sounds: enabled }); feedbackSound(enabled);
            }} /><span className="track" />
            <span className="stack"><strong>{t("sound_feedback")}</strong><span className="small">{t("sound_feedback_hint")}</span></span>
          </label>

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
