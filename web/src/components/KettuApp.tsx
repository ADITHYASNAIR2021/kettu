"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getLimits, submitNote, waitForJob, type Limits, type NoteResult } from "@/lib/api";
import { errorText, translator } from "@/lib/i18n";
import { htmlLang } from "@/lib/languages";
import { deviceId, loadPrefs, savePrefs, type Prefs } from "@/lib/prefs";
import { takeSharedAudio } from "@/lib/share";
import { AppContext } from "./AppContext";
import { Home } from "./Home";
import { Gear } from "./Icons";
import { Onboarding } from "./Onboarding";
import { ReplySheet } from "./ReplySheet";
import { ResultView } from "./ResultView";
import { SettingsSheet } from "./SettingsSheet";
import { Working, type Phase } from "./Working";

type View =
  | { name: "home" }
  | { name: "working"; phase: Phase }
  | { name: "result"; result: NoteResult };

/** How the page was opened: "1" = a voice note was shared from WhatsApp; other values = share failed. */
function sharedParam(): string | null {
  return new URLSearchParams(window.location.search).get("shared");
}

function isSharedToken(value: string | null): value is string {
  return value === "1" || /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value ?? "");
}

// Rendered client-only (see page.tsx), so first state can read localStorage directly.
export default function KettuApp() {
  const [prefs, setPrefsState] = useState<Prefs>(loadPrefs);
  const [device] = useState(deviceId);
  const [shared] = useState(sharedParam);
  const [view, setView] = useState<View>({ name: "home" });
  const [audio, setAudio] = useState<Blob | null>(null);
  const [orders, setOrders] = useState(false);
  const [limits, setLimits] = useState<Limits | null>(null);
  const [notice, setNotice] = useState<string | null>(() =>
    shared && !isSharedToken(shared) ? translator(loadPrefs().uiLang)(shared === "too_big" ? "err_too_big" : "share_missing") : null,
  );
  const [sheet, setSheetState] = useState<"reply" | "compose" | "settings" | null>(null);
  const dialogTrigger = useRef<HTMLElement | null>(null);
  const setSheet = useCallback((name: "reply" | "compose" | "settings" | null) => {
    if (name) dialogTrigger.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setSheetState(name);
  }, []);
  const [composeText, setComposeText] = useState("");
  const [dragging, setDragging] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const pendingShare = useRef<File | null>(null);

  const t = useMemo(() => translator(prefs.uiLang), [prefs.uiLang]);

  const setPrefs = useCallback((p: Partial<Prefs>) => {
    setPrefsState((prev) => {
      const next = { ...prev, ...p };
      savePrefs(next);
      return next;
    });
  }, []);

  const refreshLimits = useCallback((id: string) => {
    getLimits(id).then(setLimits).catch(() => undefined);
  }, []);

  const process = useCallback(
    async (blob: Blob, filename: string) => {
      if (!prefs.myLang || !prefs.consented) return;
      abort.current?.abort();
      const ctl = new AbortController();
      abort.current = ctl;
      setNotice(null);
      setAudio(blob);
      setView({ name: "working", phase: { kind: "upload" } });
      try {
        const { job_id, position } = await submitNote({
          audio: blob, filename, myLang: prefs.myLang, deviceId: device,
          mode: orders ? "orders" : "listen", keyterms: prefs.keyterms,
        });
        if (ctl.signal.aborted) return;
        setView({ name: "working", phase: { kind: "job", stage: "queued", position } });
        const result = await waitForJob(
          job_id,
          (s) => !ctl.signal.aborted && setView({ name: "working", phase: { kind: "job", stage: s.stage, position: s.position } }),
          ctl.signal,
        );
        if (ctl.signal.aborted) return;
        setView({ name: "result", result });
        setOrders(false);
      } catch (e) {
        if (ctl.signal.aborted) return;
        const msg = e instanceof ApiError ? errorText(t, e.code, e.message) : t("err_offline");
        setNotice(msg);
        setView({ name: "home" });
      } finally {
        refreshLimits(device);
      }
    },
    [prefs.myLang, prefs.consented, prefs.keyterms, device, orders, t, refreshLimits],
  );

  // First load: limits, and pick up any voice note shared from WhatsApp.
  useEffect(() => {
    refreshLimits(device);
    if (!shared) return;
    window.history.replaceState(null, "", "/");
    if (isSharedToken(shared)) {
      takeSharedAudio(shared).then((f) => {
        if (f) pendingShare.current = f;
        else setNotice(translator(loadPrefs().uiLang)("share_missing"));
      });
    }
  }, [device, shared, refreshLimits]);

  useEffect(() => () => abort.current?.abort(), []);

  // A shared note waits until the person has finished first-run setup.
  useEffect(() => {
    if (!prefs.myLang || !prefs.consented) return;
    const id = setInterval(() => {
      const f = pendingShare.current;
      if (f) {
        pendingShare.current = null;
        process(f, f.name);
      }
    }, 150);
    return () => clearInterval(id);
  }, [prefs.myLang, prefs.consented, process]);

  // Drag and drop anywhere on desktop.
  useEffect(() => {
    const over = (e: DragEvent) => { e.preventDefault(); setDragging(true); };
    const leave = (e: DragEvent) => { if (!e.relatedTarget) setDragging(false); };
    const drop = (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer?.files?.[0];
      if (f && prefs.consented) process(f, f.name);
    };
    window.addEventListener("dragover", over);
    window.addEventListener("dragleave", leave);
    window.addEventListener("drop", drop);
    return () => {
      window.removeEventListener("dragover", over);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("drop", drop);
    };
  }, [process, prefs.consented]);

  useEffect(() => {
    document.documentElement.lang = prefs.uiLang;
  }, [prefs.uiLang]);

  const ctx = useMemo(() => ({ t, prefs, setPrefs, device, dialogTrigger }), [t, prefs, setPrefs, device]);
  const onboarded = Boolean(prefs.myLang && prefs.consented);

  return (
    <AppContext.Provider value={ctx}>
      <main inert={sheet !== null} className={`shell${dragging ? " dropzone-active" : ""}`} data-drop={t("drop")} lang={htmlLang(prefs.uiLang)}>
        <header className="topbar">
          <button className="wordmark" onClick={() => {
            if (view.name !== "working") { setAudio(null); setView({ name: "home" }); }
          }} aria-label="Kettu">
            <b>Kettu</b><span lang="ml">കേട്ടു</span>
          </button>
          {onboarded && (
            <button className="icon-btn" onClick={() => setSheet("settings")} aria-label={t("settings")}><Gear /></button>
          )}
        </header>

        {!onboarded && <Onboarding />}

        {onboarded && view.name === "home" && (
          <Home onAudio={process} orders={orders} setOrders={setOrders} limits={limits} notice={notice}
                onCompose={() => { setComposeText(""); setSheet("compose"); }} />
        )}

        {onboarded && view.name === "working" && (
          <Working
            phase={view.phase}
            onCancel={() => {
              abort.current?.abort();
              setAudio(null);
              setView({ name: "home" });
            }}
          />
        )}

        {onboarded && view.name === "result" && (
          <ResultView
            result={view.result}
            audio={audio}
            onReply={() => setSheet("reply")}
            onSendOther={() => {
              const r = view.result;
              setComposeText(r.same_language ? r.transcript : r.translation_live !== false ? (r.translation ?? "") : "");
              setSheet("compose");
            }}
            onNew={() => { setAudio(null); setView({ name: "home" }); }}
          />
        )}

        <footer className="small" style={{ marginTop: "auto", textAlign: "center", paddingTop: 12 }}>
          Built on Gnani Prisma &amp; Timbre · <a href="/privacy">{t("privacy")}</a>
        </footer>
      </main>

      {sheet === "reply" && view.name === "result" && view.result.detected_lang && prefs.myLang && (
        <ReplySheet
          from={prefs.myLang}
          to={view.result.detected_lang}
          onClose={() => setSheet(null)}
          repliesLeft={limits?.replies_left ?? null}
          onSpent={() => refreshLimits(device)}
        />
      )}
      {sheet === "compose" && prefs.myLang && (
        <ReplySheet
          compose
          from={prefs.myLang}
          to={prefs.myLang === "hi-IN" ? "en-IN" : "hi-IN"}
          initialText={composeText}
          onClose={() => setSheet(null)}
          repliesLeft={limits?.replies_left ?? null}
          onSpent={() => refreshLimits(device)}
        />
      )}
      {sheet === "settings" && <SettingsSheet onClose={() => setSheet(null)} />}
    </AppContext.Provider>
  );
}
