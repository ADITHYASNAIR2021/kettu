"use client";

import { useState, type Dispatch, type SetStateAction } from "react";
import type { DraftAction } from "@/lib/cards";
import { htmlLang, type LangCode } from "@/lib/languages";
import { useApp } from "./AppContext";
import { Copy } from "./Icons";
import { feedbackSound } from "@/lib/sounds";

const FIELDS = ["task", "quantity", "person", "deadline"] as const;

type Props = {
  actions: DraftAction[];
  setActions: Dispatch<SetStateAction<DraftAction[]>>;
  reviewed: boolean;
  busy: boolean;
  available: boolean;
  language: LangCode;
  sourceLanguage: LangCode | null;
  onExtract: () => void;
};

export function ActionCard({ actions, setActions, reviewed, busy, available, language, sourceLanguage, onExtract }: Props) {
  const { t, prefs } = useApp();
  const [editing, setEditing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const labels = { task: t("action_task"), quantity: t("action_quantity"), person: t("action_person"), deadline: t("action_deadline") };

  const update = (id: string, field: typeof FIELDS[number], value: string) => {
    setActions((previous) => previous.map((item) => item.id === id
      ? { ...item, [field]: { value, source_text: "" }, edited: true } : item));
    setCopied(false);
  };

  const add = () => {
    setActions((previous) => [...previous, {
      id: crypto.randomUUID(), completed: false, edited: true,
      task: { value: "", source_text: "" }, quantity: { value: "", source_text: "" },
      person: { value: "", source_text: "" }, deadline: { value: "", source_text: "" },
    }]);
    setEditing(true);
    setCopied(false);
  };

  const copy = async () => {
    setCopyError(false);
    try {
      const text = actions.filter((item) => item.task.value.trim()).map((item) =>
        `${item.completed ? "☑" : "☐"} ${item.task.value}\n` + FIELDS.slice(1).map((field) =>
          `${labels[field]}: ${item[field].value.trim() || t("not_specified")}`).join("\n")
      ).join("\n\n");
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch { setCopyError(true); }
  };

  return (
    <section className="card stack action-card" aria-label={t("action_card")}>
      <div className="row">
        <h2 className="title">{t("action_card")}</h2>
        <span className="spacer" />
        {actions.length > 0 && <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => setEditing(!editing)}>
          {editing ? t("done") : t("edit_actions")}
        </button>}
      </div>
      {reviewed && !actions.length && <p style={{ margin: 0 }}>{t("no_actions")}</p>}
      {!reviewed && !actions.length && <button className="btn btn-leaf btn-block" disabled={busy || !available} onClick={onExtract}>
        {busy ? t("updating_note") : t("make_action_card")}
      </button>}
      {!available && !reviewed && <p className="small" style={{ margin: 0 }}>{t("actions_off")}</p>}
      {actions.map((item, index) => {
        const quotes = [...new Set(FIELDS.map((field) => item[field].source_text).filter(Boolean))];
        return <article className="action-item stack" key={item.id} aria-label={t("action_number", { n: index + 1 })}>
          <div className="row">
            <label className="action-complete">
              <input type="checkbox" disabled={busy} checked={item.completed} aria-label={t("complete_action", { n: index + 1 })}
                onChange={(event) => {
                  const checked = event.currentTarget.checked;
                  if (checked) feedbackSound(prefs.sounds);
                  setActions((previous) => previous.map((row) => row.id === item.id ? { ...row, completed: checked } : row));
                  setCopied(false);
                }} />
              <span>{t("action_number", { n: index + 1 })}</span>
            </label>
            <span className="spacer" />
            {item.edited && <span className="small">{t("your_edits")}</span>}
            {editing && <button className="btn btn-ghost btn-sm" disabled={busy} aria-label={t("remove_action", { n: index + 1 })}
              onClick={() => { setActions((previous) => previous.filter((row) => row.id !== item.id)); setCopied(false); }}>{t("remove")}</button>}
          </div>
          {editing ? FIELDS.map((field) => <label className="stack" style={{ gap: 4 }} key={field}>
            <span className="eyebrow">{labels[field]}</span>
            {field === "task" ? <textarea className="input" disabled={busy} rows={2} maxLength={300} value={item[field].value}
              lang={htmlLang(language)} onChange={(event) => update(item.id, field, event.target.value)} />
              : <input className="input" disabled={busy} maxLength={300} value={item[field].value} placeholder={t("not_specified")}
                lang={htmlLang(language)} onChange={(event) => update(item.id, field, event.target.value)} />}
          </label>) : <>
            <p className="action-task" data-completed={item.completed} lang={htmlLang(language)}>{item.task.value || t("not_specified")}</p>
            <dl className="action-details">{FIELDS.slice(1).map((field) => <div key={field}>
              <dt>{labels[field]}</dt><dd lang={htmlLang(language)}>{item[field].value || t("not_specified")}</dd>
            </div>)}</dl>
          </>}
          {quotes.length > 0 && <details className="action-sources"><summary>{t("source_words")}</summary>
            {quotes.map((quote) => <blockquote key={quote} lang={htmlLang(sourceLanguage)}>{quote}</blockquote>)}
          </details>}
        </article>;
      })}
      <div className="row">
        <button className="btn btn-ghost btn-sm" onClick={add} disabled={actions.length >= 8 || busy}>{t("add_action")}</button>
        {actions.some((item) => item.task.value.trim()) && <button className="btn btn-ghost btn-sm" onClick={copy}>
          <Copy /> {copied ? t("copied") : t("copy_action_card")}
        </button>}
      </div>
      {copyError && <p className="small" role="alert">{t("copy_failed")}</p>}
    </section>
  );
}
