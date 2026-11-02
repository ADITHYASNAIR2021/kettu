"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const BARS = 28;

function pickMime(): string {
  if (typeof MediaRecorder === "undefined") return "";
  for (const m of ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"]) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return "";
}

/** Tap-to-start / tap-to-stop recorder with live level bars. iPhone Safari records audio/mp4. */
export function useRecorder(onDone: (blob: Blob) => void, maxSeconds = 180) {
  const [recording, setRecording] = useState(false);
  const [starting, setStarting] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [levels, setLevels] = useState<number[]>(() => Array(BARS).fill(0.05));
  const [error, setError] = useState<string | null>(null);

  const rec = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const ctx = useRef<AudioContext | null>(null);
  const raf = useRef<number>(0);
  const started = useRef(0);
  const generation = useRef(0);
  const acquiring = useRef(false);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  }, [onDone]);

  const cleanup = useCallback(() => {
    cancelAnimationFrame(raf.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    ctx.current?.close().catch(() => undefined);
    ctx.current = null;
  }, []);

  const stop = useCallback(() => {
    if (rec.current && rec.current.state !== "inactive") rec.current.stop();
    setRecording(false);
  }, []);

  const start = useCallback(async () => {
    if (acquiring.current || rec.current?.state === "recording") return;
    acquiring.current = true;
    setStarting(true);
    const current = ++generation.current;
    setError(null);
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      if (generation.current !== current) {
        s.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = s;
      const mime = pickMime();
      const r = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = () => {
        cleanup();
        const blob = new Blob(chunks, { type: r.mimeType || mime || "audio/webm" });
        if (blob.size > 0) done.current(blob);
      };
      rec.current = r;
      r.start(250);
      started.current = performance.now();
      setSeconds(0);
      setRecording(true);

      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ac = new AC();
      ctx.current = ac;
      const analyser = ac.createAnalyser();
      analyser.fftSize = 512;
      ac.createMediaStreamSource(s).connect(analyser);
      const data = new Uint8Array(analyser.fftSize);
      const history: number[] = Array(BARS).fill(0.05);
      let last = 0;
      const tick = (now: number) => {
        const secs = (now - started.current) / 1000;
        if (now - last > 90) {
          analyser.getByteTimeDomainData(data);
          let peak = 0;
          for (const v of data) peak = Math.max(peak, Math.abs(v - 128) / 128);
          history.push(Math.min(1, 0.06 + peak * 1.8));
          history.shift();
          setLevels([...history]);
          setSeconds(Math.floor(secs));
          last = now;
        }
        if (secs >= maxSeconds) {
          r.stop();
          setRecording(false);
          return;
        }
        raf.current = requestAnimationFrame(tick);
      };
      raf.current = requestAnimationFrame(tick);
    } catch {
      if (rec.current && rec.current.state !== "inactive") {
        rec.current.onstop = null;
        rec.current.stop();
      }
      cleanup();
      setRecording(false);
      setError("mic");
    } finally {
      acquiring.current = false;
      setStarting(false);
    }
  }, [cleanup, maxSeconds]);

  useEffect(() => () => {
    generation.current += 1;
    if (rec.current && rec.current.state !== "inactive") {
      rec.current.onstop = null;
      rec.current.stop();
    }
    cleanup();
  }, [cleanup]);

  return { recording, starting, seconds, levels, error, start, stop, toggle: recording ? stop : start };
}

export function mmss(s: number) {
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
}
