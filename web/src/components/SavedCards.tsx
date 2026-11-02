"use client";

import { useCallback, useEffect, useState } from "react";
import { deleteCard, listCards } from "@/lib/card-store";
import type { ReplySeed, SavedCard } from "@/lib/cards";
import { CardWorkspace } from "./CardWorkspace";
import { useApp } from "./AppContext";

export function SavedCards({ onBack, onReply }: { onBack: () => void; onReply: (seed: ReplySeed) => void }) {
  const { t } = useApp();
  const [cards, setCards] = useState<SavedCard[]>([]);
  const [selected, setSelected] = useState<SavedCard | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(() => {
    setLoading(true); setError(null);
    listCards().then(setCards).catch(() => setError(t("storage_failed"))).finally(() => setLoading(false));
  }, [t]);
  useEffect(() => {
    let active = true;
    listCards().then((items) => { if (active) setCards(items); })
      .catch(() => { if (active) setError(t("storage_failed")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [t]);

  return <section className="stack">
    <h1 className="title">{t("saved_cards")}</h1>
    <p className="small" style={{ margin: 0 }}>{t("device_storage_notice")}</p>
    <button className="btn btn-ghost btn-block" onClick={() => {
      if (selected) { setSelected(null); refresh(); } else onBack();
    }}>{t("back")}</button>
    {selected ? <>
      <h2 className="title">{selected.title}</h2>
      <CardWorkspace key={selected.id} savedCard={selected} language={selected.language} sourceLanguage={selected.sourceLanguage}
        onReply={onReply} onSaved={(card) => {
          setSelected(card);
          setCards((previous) => previous.map((item) => item.id === card.id ? card : item));
        }} />
      <button className="btn btn-ghost btn-block" onClick={async () => {
        if (!window.confirm(t("delete_card_confirm", { title: selected.title }))) return;
        try { await deleteCard(selected.id); setSelected(null); refresh(); }
        catch { setError(t("storage_failed")); }
      }}>{t("delete_card")}</button>
    </> : <>
      <label className="stack"><span className="eyebrow">{t("search_cards")}</span>
        <input className="input" type="search" value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <p className="small">{cards.length}/50</p>
      {loading ? <p role="status">…</p> : cards.filter((card) => `${card.title} ${card.actions.map((item) => item.task).join(" ")}`
        .toLocaleLowerCase().includes(query.toLocaleLowerCase())).map((card) => <button className="card saved-card-link" key={card.id} onClick={() => setSelected(card)}>
          <strong>{card.title}</strong><span className="small">{card.actions.filter((item) => item.completed).length}/{card.actions.length} · {new Date(card.updatedAt).toLocaleDateString()}</span>
        </button>)}
      {!loading && !cards.length && !error && <p>{t("no_saved_cards")}</p>}
      {error && <button className="btn btn-ghost" onClick={refresh}>{t("try_again")}</button>}
    </>}
    {error && <div className="alert" role="alert">{error}</div>}
  </section>;
}
