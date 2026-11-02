"use client";

import { useState, type SetStateAction } from "react";
import type { ActionItem } from "@/lib/api";
import { cardActions, cardText, draftActions, editableActions, makeCard, type DraftAction, type ReplySeed, type SavedCard } from "@/lib/cards";
import { saveCard } from "@/lib/card-store";
import type { LangCode } from "@/lib/languages";
import { download } from "@/lib/share";
import { ActionCard } from "./ActionCard";
import { ConfirmationBuilder } from "./ConfirmationBuilder";
import { useApp } from "./AppContext";

export function CardWorkspace({ items = [], savedCard, language, sourceLanguage, reviewed = true, busy = false,
  available = false, onExtract = () => {}, onReply, onSaved }: {
  items?: ActionItem[]; savedCard?: SavedCard; language: LangCode; sourceLanguage: LangCode | null;
  reviewed?: boolean; busy?: boolean; available?: boolean; onExtract?: () => void;
  onReply: (seed: ReplySeed) => void; onSaved?: (card: SavedCard) => void;
}) {
  const { t, online } = useApp();
  const [actions, setActions] = useState(() => savedCard ? editableActions(savedCard.actions) : draftActions(items));
  const [stored, setStored] = useState(savedCard);
  const [title, setTitle] = useState(savedCard?.title ?? items[0]?.task.value.slice(0, 80) ?? "");
  const [saveOpen, setSaveOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const values = cardActions(actions);

  const changeActions = (update: SetStateAction<DraftAction[]>) => {
    setActions(update); setSaved(false); setConfirming(false);
  };
  const persist = async () => {
    setSaving(true); setError(null);
    try {
      const card = makeCard(actions, language, sourceLanguage, title, stored);
      await saveCard(card);
      setStored(card); setSaved(true); setSaveOpen(false); onSaved?.(card);
    } catch (error) { setError(t(error instanceof Error && error.message === "cards_full" ? "cards_full" : "storage_failed")); }
    finally { setSaving(false); }
  };

  return <div className="stack">
    <ActionCard actions={actions} setActions={changeActions} reviewed={reviewed} busy={busy || saving}
      available={available && online} language={language} sourceLanguage={sourceLanguage} onExtract={onExtract} />
    {values.length > 0 && <div className="row card-tools">
      <button className="btn btn-ghost btn-sm" disabled={busy || saving} onClick={() => {
        if (!title.trim()) setTitle(values[0].task.slice(0, 80));
        setSaveOpen(!saveOpen); setError(null);
      }}>{saved ? t("card_saved") : t("save_device")}</button>
      <button className="btn btn-leaf btn-sm" disabled={busy || saving} onClick={() => setConfirming(!confirming)}>{t("prepare_confirmation")}</button>
      <button className="btn btn-ghost btn-sm" onClick={() => {
        const card = makeCard(actions, language, sourceLanguage, title.trim() || values[0].task.slice(0, 80), stored);
        const text = cardText(card, { task: t("action_task"), quantity: t("action_quantity"), person: t("action_person"), deadline: t("action_deadline") });
        download(new Blob([text], { type: "text/plain;charset=utf-8" }), "kettu-card.txt");
      }}>{t("export_card")}</button>
    </div>}
    {saveOpen && <section className="card stack" aria-label={t("save_device")}>
      <p className="small" style={{ margin: 0 }}>{t("device_storage_notice")}</p>
      <label className="stack"><span className="eyebrow">{t("card_nickname")}</span>
        <input className="input" maxLength={80} value={title} disabled={saving} onChange={(event) => { setTitle(event.target.value); setSaved(false); }} />
      </label>
      <button className="btn btn-primary btn-block" disabled={saving || !title.trim() || !values.length} onClick={persist}>
        {saving ? "…" : t("save_card")}</button>
      <button className="btn btn-ghost btn-block" disabled={saving} onClick={() => setSaveOpen(false)}>{t("cancel")}</button>
    </section>}
    {saved && <p className="small" role="status">{t("card_saved")}</p>}
    {error && <div className="alert" role="alert">{error}</div>}
    {confirming && <ConfirmationBuilder actions={values} language={language} sourceLanguage={sourceLanguage}
      onClose={() => setConfirming(false)} onReply={onReply} />}
  </div>;
}
