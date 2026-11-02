"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, extFor, submitNote, translateText, waitForJob, type Limits } from "@/lib/api";
import { canHandOff, direction, otherSpeaker, turnFromNote, type ConversationConfig, type ConversationTurn } from "@/lib/conversation";
import { errorText } from "@/lib/i18n";
import { htmlLang, lang, LANGUAGES, type LangCode } from "@/lib/languages";
import type { PendingJob } from "@/lib/pending-job";
import { feedbackSound } from "@/lib/sounds";
import { useApp } from "./AppContext";
import { Mic, Stop } from "./Icons";
import { ReadAloud } from "./ResultView";
import { useRecorder, mmss } from "./useRecorder";
import { useObjectUrl } from "./useObjectUrl";
import { Working, type Phase } from "./Working";

export function ConversationMode({ initialJob, onAccepted, onConsumed, onSpent, onBack, limits }: {
  initialJob?: PendingJob; onAccepted: (job: PendingJob) => void; onConsumed: (job: null) => void;
  onSpent: () => void; onBack: (message?: string) => void; limits: Limits | null;
}) {
  const { t, prefs, device, online } = useApp();
  const [config, setConfig] = useState<ConversationConfig>(() => initialJob?.conversation ?? { a: prefs.myLang ?? "en-IN", b: prefs.myLang === "hi-IN" ? "en-IN" : "hi-IN", speaker: "a" });
  const [started, setStarted] = useState(Boolean(initialJob));
  const [phase, setPhase] = useState<Phase | null>(initialJob ? { kind: "job", stage: "queued", position: 0 } : null);
  const [uploading, setUploading] = useState(false);
  const [waiting, setWaiting] = useState<PendingJob | null>(null);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [turn, setTurn] = useState<ConversationTurn | null>(null);
  const [words, setWords] = useState("");
  const [source, setSource] = useState<LangCode>(direction(config).from);
  const [checked, setChecked] = useState(false);
  const [handed, setHanded] = useState(false);
  const [history, setHistory] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [audio, setAudio] = useState<Blob | null>(null);
  const [localRecording, setLocalRecording] = useState(false);
  const audioUrl = useObjectUrl(audio);
  const controller = useRef<AbortController | null>(null);
  const file = useRef<HTMLInputElement | null>(null);
  const inFlight = useRef(false);
  const consumed = useRef(new Set<string>());
  const { from, to } = direction(config);
  const person = (speaker: "a" | "b") => t(speaker === "a" ? "person_a" : "person_b");
  const available = online && limits?.service_open !== false && (limits?.notes_left ?? 1) > 0;

  const poll = useCallback(async (job: PendingJob, ctl: AbortController) => {
    let terminal = false;
    try {
      const result = await waitForJob(job.id, (state) => {
        terminal = state.status === "error";
        if (!ctl.signal.aborted) setPhase({ kind: "job", stage: state.stage, position: state.position });
      }, ctl.signal);
      if (ctl.signal.aborted) return;
      const next = turnFromNote(result, job.conversation!);
      consumed.current.add(job.id);
      setWaiting(null);
      setTurn(next); setWords(next.text); setSource(next.from); setChecked(false); setHanded(false);
      onConsumed(null);
    } catch (error) {
      if (ctl.signal.aborted) return;
      if (terminal || (error instanceof ApiError && error.code === "not_found")) { consumed.current.add(job.id); onConsumed(null); }
      else setWaiting(job);
      setError(error instanceof ApiError ? errorText(t, error.code, error.message) : t("err_offline"));
    } finally { if (!ctl.signal.aborted) setPhase(null); onSpent(); }
  }, [onConsumed, onSpent, t]);

  useEffect(() => {
    if (!initialJob?.conversation || consumed.current.has(initialJob.id)) return;
    const ctl = new AbortController(); controller.current = ctl;
    void Promise.resolve().then(() => { if (!ctl.signal.aborted) return poll(initialJob, ctl); });
    return () => ctl.abort();
  }, [initialJob, poll]);
  useEffect(() => () => controller.current?.abort(), []);

  const submit = useCallback(async (blob: Blob) => {
    if (inFlight.current || turn) return;
    if (!available) {
      setAudio(blob); setLocalRecording(true);
      setError(t(!online ? "err_offline" : limits?.service_open === false ? "err_service_budget" : "err_daily_limit"));
      return;
    }
    setLocalRecording(false);
    inFlight.current = true; setUploading(true); setPhase({ kind: "upload" }); setError(null); setAudio(blob);
    const ctl = new AbortController(); controller.current = ctl;
    try {
      const accepted = await submitNote({ audio: blob, filename: "conversation" + extFor(blob.type), myLang: to, deviceId: device, mode: "listen" });
      const receipt: PendingJob = { id: accepted.job_id, myLang: to, submittedAt: Date.now(), conversation: { ...config } };
      onAccepted(receipt); setUploading(false);
      if (!ctl.signal.aborted) await poll(receipt, ctl);
    } catch (error) {
      if (!ctl.signal.aborted) {
        setPhase(null); setError(error instanceof ApiError && !["offline", "model_timeout"].includes(error.code)
          ? errorText(t, error.code, error.message) : t("upload_unconfirmed"));
      }
    } finally { inFlight.current = false; setUploading(false); onSpent(); }
  }, [available, turn, to, device, config, onAccepted, poll, t, onSpent, online, limits?.service_open]);
  const rec = useRecorder(submit, 60);

  const translate = async (text: string, sourceLang: LangCode, existing: ConversationTurn | null) => {
    if (inFlight.current || !online || !text.trim() || text.length > 6000) return;
    inFlight.current = true; setBusy(true); setError(null); setChecked(false);
    const ctl = new AbortController(); controller.current = ctl;
    try {
      const result = await translateText({ text, fromLang: sourceLang, toLang: to, deviceId: device, signal: ctl.signal });
      if (ctl.signal.aborted) return;
      const next: ConversationTurn = { id: existing?.id ?? crypto.randomUUID(), speaker: config.speaker, from: sourceLang, to,
        text, translation: result.translation, live: result.translation_live, missing: result.missing_facts };
      setTurn(next); setWords(text); setSource(sourceLang); setTyping(false);
      if (!existing) { setAudio(null); setLocalRecording(false); }
    } catch (error) {
      if (!ctl.signal.aborted) setError(error instanceof ApiError ? errorText(t, error.code, error.message) : t("err_offline"));
    } finally { inFlight.current = false; if (!ctl.signal.aborted) setBusy(false); onSpent(); }
  };

  const leave = () => {
    if (uploading) return;
    if (started && !window.confirm(t("conversation_leave"))) return;
    controller.current?.abort(); onBack();
  };
  const ready = canHandOff(turn, words, source, checked) && source === from;

  return <section className="stack conversation" data-speaker={config.speaker}>
    <div className="row"><h1 className="title">{t("conversation_mode")}</h1><span className="spacer" />
      <button className="btn btn-ghost btn-sm" disabled={uploading} onClick={leave}>{t("back")}</button></div>
    <p className="small">{t("conversation_privacy")}</p>
    {started && limits && <p className="small">{t("left_today", { n: limits.notes_left })}</p>}
    {!started ? <div className="card stack">
      <p className="lede">{t("conversation_intro")}</p>
      {(["a", "b"] as const).map((speaker) => <label className={`stack participant participant-${speaker}`} key={speaker}>
        <span className="eyebrow">{person(speaker)}</span><select className="input" value={config[speaker]}
          onChange={(event) => setConfig({ ...config, [speaker]: event.target.value as LangCode })}>
          {LANGUAGES.map((entry) => <option key={entry.code} value={entry.code}>{entry.native} · {entry.name}</option>)}
        </select></label>)}
      <button className="btn btn-primary btn-block" disabled={!online} onClick={() => setStarted(true)}>{t("conversation_start")}</button>
    </div> : phase ? <Working phase={phase} targetLanguage={to} onCancel={leave} cancelDisabled={uploading} /> : waiting ? <div className="card stack">
      <h2 className="title">{t("pending_note")}</h2><p>{t("pending_hint")}</p>
      <button className="btn btn-primary btn-block" disabled={!online} onClick={() => {
        const ctl = new AbortController(); controller.current = ctl;
        setWaiting(null); setError(null); setPhase({ kind: "job", stage: "queued", position: 0 }); void poll(waiting, ctl);
      }}>{t("resume_processing")}</button>
    </div> : !turn ? <>
      <div className="turn-cue" role="status"><span className="eyebrow">{person(config.speaker)}</span>
        <h2 className="display">{t("your_turn")}</h2>
        <p lang={htmlLang(from)}>{lang(from)?.native} <span aria-hidden>→</span> {lang(to)?.native}</p>
      </div>
      <div className="card stack" style={{ alignItems: "center" }}>
        <button className="rec-btn" data-on={rec.recording} disabled={busy || rec.starting || (!rec.recording && !available)} onClick={rec.toggle}
          aria-label={rec.recording ? t("stop") : t("record_turn")}>
          {rec.recording ? <Stop size={30} /> : <Mic size={30} />}</button>
        {rec.recording && <div className="bars" aria-hidden>{rec.levels.map((level, i) => <span key={i} style={{ height: 4 + level * 36 }} />)}</div>}
        <span className="small">{rec.recording ? mmss(rec.seconds) : t("short_turn_hint")}</span>
        {rec.error && <p role="alert">{t("err_mic")}</p>}
        <button className="btn btn-ghost btn-block" disabled={rec.recording || rec.starting || busy || !online} onClick={() => setTyping(!typing)}>{t("type_instead")}</button>
        <input ref={file} type="file" accept="audio/*,.opus,.ogg,.m4a,.mp3,.wav,.aac,.amr" hidden onChange={(event) => {
          const selected = event.target.files?.[0]; event.target.value = "";
          if (selected) void submit(selected);
        }} />
        <button className="btn btn-ghost btn-sm" disabled={rec.recording || rec.starting || busy || !available} onClick={() => file.current?.click()}>{t("upload")}</button>
        <span className="small">{t("conversation_file_hint")}</span>
      </div>
      {localRecording && audioUrl && audio && !rec.recording && !rec.starting && <div className="card stack">
        <p className="small">{t("unsent_recording")}</p><audio src={audioUrl} controls aria-label={t("play_original")} />
        <button className="btn btn-primary" disabled={!available || busy} onClick={() => submit(audio)}>{t("send_recording")}</button>
      </div>}
      {typing && <form className="card stack" onSubmit={(event) => { event.preventDefault(); void translate(typed, from, null); }}>
        <label className="stack"><span>{t("your_words", { lang: lang(from)?.native ?? "" })}</span>
          <textarea className="input" lang={htmlLang(from)} rows={4} value={typed} disabled={busy} onChange={(event) => setTyped(event.target.value)} /></label>
        <span className="small">{typed.length}/6000</span>
        <button className="btn btn-primary" disabled={rec.recording || rec.starting || busy || !online || !typed.trim() || typed.length > 6000}>{busy ? t("translating_turn") : t("translate")}</button>
      </form>}
    </> : !handed ? <>
      {busy && <p role="status">{t("translating_turn")}</p>}
      <h2 className="title">{t("check_turn", { person: person(config.speaker) })}</h2>
      {turn.from !== from && <p className="alert">{t("detected_different")}</p>}
      {audioUrl && <audio src={audioUrl} controls aria-label={t("play_original")} />}
      <label className="stack"><span>{t("spoken_language")}</span><select className="input" value={source} disabled={busy}
        onChange={(event) => { setSource(event.target.value as LangCode); setChecked(false); }}>
        {LANGUAGES.map((entry) => <option key={entry.code} value={entry.code}>{entry.native} · {entry.name}</option>)}
      </select></label>
      {source !== from && <button className="btn btn-ghost" disabled={busy} onClick={() => {
        setConfig({ ...config, [config.speaker]: source }); setChecked(false);
      }}>{t("use_speaker_language", { lang: lang(source)?.native ?? "", person: person(config.speaker) })}</button>}
      <label className="stack"><span>{t("transcript_words")}</span><textarea className="input" rows={4} lang={htmlLang(source)} value={words} disabled={busy}
        onChange={(event) => { setWords(event.target.value); setChecked(false); }} /></label>
      <button className="btn btn-ghost" disabled={busy || !online || !words.trim() || words.length > 6000 || (turn.live && words === turn.text && source === turn.from)}
        onClick={() => translate(words, source, turn)}>{busy ? "…" : t("refresh_turn")}</button>
      {words.length > 6000 && <p className="alert">{words.length}/6000</p>}
      {turn.live && words === turn.text && source === turn.from ? <div className="card stack">
        <span className="eyebrow">{t("in_lang", { lang: lang(to)?.native ?? "" })}</span>
        <p className="translation" lang={htmlLang(to)}>{turn.translation}</p>
        {turn.missing.length > 0 && <p className="alert">{t("missing_facts")} {turn.missing.join(" · ")}</p>}
      </div> : <p className="alert" role="status">{t("turn_needs_update")}</p>}
      <label className="action-complete card"><input type="checkbox" checked={checked} disabled={busy || !turn.live || words !== turn.text || source !== turn.from}
        onChange={(event) => { setChecked(event.target.checked); if (event.target.checked) feedbackSound(prefs.sounds); }} />{t("checked_words")}</label>
      <button className="btn btn-primary btn-block" disabled={!ready || busy} onClick={() => {
        setHanded(true); setHistory((previous) => [...previous.filter((item) => item.id !== turn.id), turn]); feedbackSound(prefs.sounds, "ready");
      }}>{t("show_other", { person: person(otherSpeaker(config.speaker)) })}</button>
    </> : <div className="stack handoff" data-speaker={otherSpeaker(config.speaker)}>
      <div className="turn-cue" role="status"><span className="eyebrow">{person(otherSpeaker(config.speaker))}</span>
        <h2 className="display">{t("pass_phone")}</h2><p>{t("read_then_reply")}</p></div>
      <div className="card stack"><p className="translation" lang={htmlLang(turn.to)}>{turn.translation}</p>
        <p className="small">{t("ai_check_hint")}</p>
        {turn.translation.length <= 900 ? <ReadAloud key={`${turn.id}:${prefs.voice}`} text={turn.translation} lang={turn.to} label={t("generate_turn_voice")} />
          : <p className="small">{t("turn_voice_long")}</p>}
      </div>
      <button className="btn btn-primary btn-block" onClick={() => {
        setConfig({ ...config, speaker: otherSpeaker(config.speaker) }); setTurn(null); setWords(""); setTyped(""); setTyping(false);
        setAudio(null); setChecked(false); setHanded(false); setError(null); feedbackSound(prefs.sounds);
      }}>{t("reply_in", { lang: lang(turn.to)?.native ?? "" })}</button>
      <button className="btn btn-ghost btn-block" onClick={() => {
        setHanded(false); setChecked(false); setHistory((previous) => previous.filter((item) => item.id !== turn.id));
      }}>{t("check_turn_again")}</button>
    </div>}
    {error && <div className="alert" role="alert">{error}</div>}
    {history.length > 0 && <details className="card orig"><summary>{t("conversation_history", { n: history.length })}</summary>
      <div className="stack">{history.map((item) => <article className={`conversation-message participant-${item.speaker}`} key={item.id}>
        <strong>{person(item.speaker)} · {lang(item.from)?.native} → {lang(item.to)?.native}</strong>
        <p lang={htmlLang(item.from)}>{item.text}</p><p lang={htmlLang(item.to)}>{item.translation}</p>
      </article>)}</div></details>}
  </section>;
}
