import type { LangCode } from "./languages";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type Entity = {
  type: "time" | "date" | "amount" | "quantity" | "name" | "place";
  value: string;
  source_text: string;
  in_translation?: string;
};

export type OrderItem = { item: string; quantity: string; unit: string };
export type ActionDetail = { value: string; source_text: string };
export type ActionItem = { task: ActionDetail; quantity: ActionDetail; person: ActionDetail; deadline: ActionDetail };

export type NoteResult = {
  detected_lang: LangCode | null;
  my_lang: LangCode;
  duration_s: number;
  transcript: string;
  translation: string | null;
  gist: string | null;
  entities: Entity[];
  order_items: OrderItem[] | null;
  same_language: boolean;
  missing_facts: string[];
  translation_live: boolean;
  speech_live?: boolean;
  timings_ms: Record<string, number>;
  action_items?: ActionItem[];
  actions_reviewed?: boolean;
  original_transcript?: string;
  transcript_edited?: boolean;
  revision?: number;
};

export type NoteReview = Pick<NoteResult,
  "transcript" | "detected_lang" | "my_lang" | "translation" | "gist" | "entities" |
  "missing_facts" | "order_items" | "same_language" | "translation_live"
> & { action_items: ActionItem[]; actions_reviewed: boolean };

export type TextTranslation = {
  to_lang: LangCode;
  translation: string;
  entities: Entity[];
  missing_facts: string[];
  translation_live: boolean;
};

export type JobState = {
  status: "queued" | "processing" | "done" | "error";
  position: number;
  stage: string;
  result?: NoteResult;
  error?: { code: string; message: string };
};

export type ReplyDraft = { target_text: string; back_translation: string; source_text: string };
export type Limits = { notes_left: number; replies_left: number; service_open: boolean; translation_live?: boolean; speech_live?: boolean };
export type Voice = "female" | "male";

export class ApiError extends Error {
  constructor(public code: string, message: string, public status = 0) {
    super(message);
  }
}

async function parse<T>(resp: Response): Promise<T> {
  if (resp.ok) return (await resp.json()) as T;
  let code = "internal";
  let message = "Something went wrong. Please try again.";
  try {
    const body = await resp.json();
    code = body?.error?.code ?? code;
    message = body?.error?.message ?? message;
  } catch {
    /* non-JSON error */
  }
  throw new ApiError(code, message, resp.status);
}

async function call(input: string, init?: RequestInit): Promise<Response> {
  if (typeof navigator !== "undefined" && !navigator.onLine) throw new ApiError("offline", "Reconnect to use AI processing.");
  try {
    const timeout = AbortSignal.timeout(120_000);
    const signal = init?.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
    return await fetch(`${API_URL}${input}`, { ...init, signal });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      throw new ApiError("model_timeout", "Kettu took too long to respond. Please try again.");
    }
    throw new ApiError("offline", "Can't reach Kettu. Check your internet and try again.");
  }
}

export async function submitNote(opts: {
  audio: Blob;
  filename: string;
  myLang: LangCode;
  deviceId: string;
  mode: "listen" | "orders";
  keyterms?: string[];
}): Promise<{ job_id: string; position: number }> {
  const form = new FormData();
  form.append("audio", opts.audio, opts.filename);
  form.append("my_lang", opts.myLang);
  form.append("device_id", opts.deviceId);
  form.append("mode", opts.mode);
  if (opts.keyterms?.length) form.append("keyterms", JSON.stringify(opts.keyterms));
  return parse(await call("/v1/notes", { method: "POST", body: form }));
}

export async function getJob(jobId: string, signal?: AbortSignal): Promise<JobState> {
  return parse(await call(`/v1/jobs/${jobId}`, { cache: "no-store", signal }));
}

/** Polls every second until the job is done; reports queue position and stage on the way. */
export async function waitForJob(
  jobId: string,
  onUpdate: (s: JobState) => void,
  signal?: AbortSignal,
): Promise<NoteResult> {
  let misses = 0;
  const deadline = Date.now() + 15 * 60_000;
  for (;;) {
    if (Date.now() > deadline) throw new ApiError("model_timeout", "This note is taking too long. Please try again later.");
    if (signal?.aborted) throw new ApiError("aborted", "Cancelled.");
    let state: JobState;
    try {
      state = await getJob(jobId, signal);
      misses = 0;
    } catch (e) {
      if (e instanceof ApiError && e.code === "offline" && ++misses < 10) {
        await sleep(1500);
        continue;
      }
      throw e;
    }
    onUpdate(state);
    if (state.status === "done" && state.result) return state.result;
    if (state.status === "error") {
      throw new ApiError(state.error?.code ?? "internal", state.error?.message ?? "Something went wrong.");
    }
    await sleep(1000);
  }
}

export async function previewReply(opts: {
  fromLang: LangCode;
  toLang: LangCode;
  deviceId: string;
  text?: string;
  audio?: Blob;
}): Promise<ReplyDraft> {
  if (opts.audio) {
    const form = new FormData();
    form.append("audio", opts.audio, "reply" + extFor(opts.audio.type));
    form.append("from_lang", opts.fromLang);
    form.append("to_lang", opts.toLang);
    form.append("device_id", opts.deviceId);
    return parse(await call("/v1/replies/preview", { method: "POST", body: form }));
  }
  return parse(
    await call("/v1/replies/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: opts.text ?? "", from_lang: opts.fromLang, to_lang: opts.toLang, device_id: opts.deviceId }),
    }),
  );
}

export async function translateText(opts: {
  text: string;
  fromLang: LangCode | null;
  toLang: LangCode;
  deviceId: string;
  signal?: AbortSignal;
}): Promise<TextTranslation> {
  return parse(
    await call("/v1/translate", {
      method: "POST",
      signal: opts.signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: opts.text, from_lang: opts.fromLang, to_lang: opts.toLang, device_id: opts.deviceId }),
    }),
  );
}

export async function reviewNote(opts: {
  text: string;
  sourceLang: LangCode | null;
  myLang: LangCode;
  duration: number;
  mode: "listen" | "orders";
  deviceId: string;
  signal?: AbortSignal;
}): Promise<NoteReview> {
  return parse(await call("/v1/notes/review", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: opts.signal,
    body: JSON.stringify({ text: opts.text, source_lang: opts.sourceLang, my_lang: opts.myLang,
      duration_s: opts.duration, mode: opts.mode, device_id: opts.deviceId }),
  }));
}

export async function speakReply(opts: {
  targetText: string;
  toLang: LangCode;
  voice: Voice;
  deviceId: string;
  purpose?: "reply" | "read_aloud";
}): Promise<Blob> {
  const resp = await call("/v1/replies/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_text: opts.targetText,
      to_lang: opts.toLang,
      voice: opts.voice,
      device_id: opts.deviceId,
      format: "mp3",
      purpose: opts.purpose ?? "reply",
    }),
  });
  if (!resp.ok) await parse(resp);
  return resp.blob();
}

export async function getLimits(deviceId: string): Promise<Limits> {
  return parse(await call(`/v1/limits?device_id=${encodeURIComponent(deviceId)}`, { cache: "no-store" }));
}

export function extFor(mime: string): string {
  if (mime.includes("webm")) return ".webm";
  if (mime.includes("mp4") || mime.includes("m4a") || mime.includes("aac")) return ".m4a";
  if (mime.includes("mpeg") || mime.includes("mp3")) return ".mp3";
  if (mime.includes("wav")) return ".wav";
  return ".ogg";
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
