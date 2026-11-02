"use client";

import { useState } from "react";
import { CARD_FIELDS, type CardAction, type CardField, type ReplySeed } from "@/lib/cards";
import { confirmationText } from "@/lib/confirmation";
import { htmlLang, LANGUAGES, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { feedbackSound } from "@/lib/sounds";

export function ConfirmationBuilder({ actions, language, sourceLanguage, onReply, onClose }: {
  actions: CardAction[]; language: LangCode; sourceLanguage: LangCode | null;
  onReply: (seed: ReplySeed) => void; onClose: () => void;
}) {
  const { t, online, prefs } = useApp();
  const [selection, setSelection] = useState<Record<string, CardField[]>>(() => Object.fromEntries(
    actions.map((action) => [action.id, CARD_FIELDS.filter((field) => action[field].trim())])));
  const [custom, setCustom] = useState<string | null>(null);
  const [target, setTarget] = useState<LangCode | "">(sourceLanguage ?? "");
  const text = custom ?? confirmationText(actions, selection, language);
  const labels = { task: t("action_task"), quantity: t("action_quantity"), person: t("action_person"), deadline: t("action_deadline") };
  return <section className="card stack" aria-label={t("prepare_confirmation")}>
    <h2 className="title">{t("prepare_confirmation")}</h2>
    <p className="small" style={{ margin: 0 }}>{t("confirmation_hint")}</p>
    {actions.map((action, index) => <fieldset className="confirmation-fields" key={action.id}>
      <legend>{t("action_number", { n: index + 1 })}</legend>
      {CARD_FIELDS.filter((field) => action[field].trim()).map((field) => <label key={field}>
        <input type="checkbox" checked={selection[action.id]?.includes(field) ?? false}
          onChange={(event) => {
            const checked = event.currentTarget.checked;
            if (checked) feedbackSound(prefs.sounds);
            setSelection((previous) => ({ ...previous, [action.id]: checked
              ? CARD_FIELDS.filter((key) => key === field || previous[action.id]?.includes(key))
              : previous[action.id].filter((key) => key !== field) }));
            setCustom(null);
          }} />
        <span><b>{labels[field]}:</b> <span lang={htmlLang(language)}>{action[field]}</span></span>
      </label>)}
    </fieldset>)}
    <label className="stack"><span className="eyebrow">{t("confirmation_draft")}</span>
      <textarea className="input" rows={6} lang={htmlLang(language)} value={text} onChange={(event) => setCustom(event.target.value)} />
    </label>
    <span className={text.length > 700 ? "alert" : "small"} role={text.length > 700 ? "alert" : undefined}>
      {text.length}/700 {text.length > 700 ? t("confirmation_too_long") : ""}
    </span>
    <label className="stack"><span className="eyebrow">{t("reply_to")}</span>
      <select className="input" value={target} onChange={(event) => setTarget(event.target.value as LangCode | "")}>
        <option value="">{t("choose_lang")}</option>
        {LANGUAGES.map((entry) => <option key={entry.code} value={entry.code}>{entry.native} · {entry.name}</option>)}
      </select>
    </label>
    <button className="btn btn-primary btn-block" disabled={!online || !target || !text.trim() || text.length > 700}
      onClick={() => target && onReply({ text, from: language, to: target })}>{t("continue_reply")}</button>
    <button className="btn btn-ghost btn-block" onClick={onClose}>{t("cancel")}</button>
  </section>;
}
