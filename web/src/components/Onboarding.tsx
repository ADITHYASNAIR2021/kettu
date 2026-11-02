"use client";

import { useState } from "react";
import { LANGUAGES, type LangCode } from "@/lib/languages";
import { uiFor } from "@/lib/prefs";
import { useApp } from "./AppContext";

/** First run: pick "my language", then a plain consent note. Two screens, nothing else. */
export function Onboarding() {
  const { t, prefs, setPrefs } = useApp();
  const [picked, setPicked] = useState<LangCode | null>(prefs.myLang);
  const [step, setStep] = useState<"lang" | "consent">("lang");

  if (step === "lang") {
    return (
      <section className="stack reveal" style={{ gap: 20 }}>
        <p className="eyebrow">കേട്ടു · heard</p>
        <h1 className="display">
          {t("tagline").split(",")[0]}
          {t("tagline").includes(",") && <em>,{t("tagline").split(",").slice(1).join(",")}</em>}
        </h1>
        <p className="lede">{t("hero_sub")}</p>
        <div className="stack" style={{ gap: 10 }}>
          <h2 className="title" style={{ fontSize: 22 }}>{t("pick_lang")}</h2>
          <div className="lang-grid" role="group" aria-label={t("pick_lang")}>
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                type="button"
                className="lang-opt"
                aria-pressed={picked === l.code}
                lang={l.code.split("-")[0]}
                onClick={() => {
                  setPicked(l.code);
                  setPrefs({ uiLang: uiFor(l.code) });
                }}
              >
                <b>{l.native}</b>
                {l.native !== l.name && <small>{l.name}</small>}
              </button>
            ))}
          </div>
        </div>
        <button
          className="btn btn-primary btn-block"
          disabled={!picked}
          onClick={() => {
            if (!picked) return;
            setPrefs({ myLang: picked });
            setStep("consent");
          }}
        >
          {t("continue")}
        </button>
      </section>
    );
  }

  return (
    <section className="stack reveal" style={{ gap: 20 }}>
      <h1 className="display" style={{ fontSize: 36 }}>{t("consent_title")}</h1>
      <div className="card stack">
        <p style={{ margin: 0, fontSize: 18 }}>{t("consent_body")}</p>
        <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
          <li>Gnani AI · Prisma (speech to text), Timbre (voice)</li>
          <li>Translation · Google Gemini / Anthropic</li>
        </ul>
        <a href="/privacy" target="_blank" rel="noopener noreferrer">{t("privacy")}</a>
      </div>
      <button className="btn btn-primary btn-block" onClick={() => setPrefs({ consented: true })}>
        {t("agree")}
      </button>
      <button className="btn btn-ghost btn-block" onClick={() => setStep("lang")}>
        {t("back")}
      </button>
    </section>
  );
}
