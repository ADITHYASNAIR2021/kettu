/** Reads the voice note the service worker parked after a WhatsApp share, then clears it. */
export async function takeSharedAudio(): Promise<File | null> {
  if (typeof caches === "undefined") return null;
  try {
    const cache = await caches.open("kettu-share-v1");
    const resp = await cache.match("/shared-audio");
    if (!resp) return null;
    await cache.delete("/shared-audio");
    const blob = await resp.blob();
    const name = decodeURIComponent(resp.headers.get("X-Filename") || "voice-note.opus");
    return new File([blob], name, { type: blob.type || "audio/ogg" });
  } catch {
    return null;
  }
}

/** Shares the reply audio back to WhatsApp (Android) or falls back to a download. */
export async function shareAudio(blob: Blob, filename: string, caption: string): Promise<"shared" | "downloaded" | "cancelled"> {
  const file = new File([blob], filename, { type: blob.type || "audio/mpeg" });
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], text: caption });
      return "shared";
    } catch (e) {
      if ((e as DOMException)?.name === "AbortError") return "cancelled";
    }
  }
  download(blob, filename);
  return "downloaded";
}

export function download(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
