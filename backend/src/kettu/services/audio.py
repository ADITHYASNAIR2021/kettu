"""Audio prep with ffmpeg: check, clean, split at pauses, encode replies.

ffmpeg runs in a worker thread (subprocess.run) so it works on every event loop, Windows included.
"""

import asyncio
import json
import logging
import math
import re
import struct
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from kettu.domain.errors import ErrorCode, KettuError

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000
SILENCE_DB = -35
SILENCE_MIN_S = 0.4
MIN_CHUNK_S = 4.0
INPUT_FORMATS = "aac,amr,asf,avi,flac,matroska,webm,mov,mp3,ogg,wav"
INPUT_OPTIONS = ["-protocol_whitelist", "file,pipe", "-format_whitelist", INPUT_FORMATS]

_SILENCE_START = re.compile(r"silence_start: (-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end: (-?[\d.]+)")


@dataclass
class ProbeInfo:
    duration_s: float
    has_audio: bool
    codec: str | None


def _run(args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, check=False)


async def run(args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    try:
        return await asyncio.to_thread(_run, args, timeout)
    except subprocess.TimeoutExpired as exc:
        raise KettuError(ErrorCode.UNSUPPORTED_FILE, "That audio could not be read in time. Try a shorter recording.") from exc


async def probe(path: Path) -> ProbeInfo:
    proc = await run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=codec_type,codec_name",
            "-of", "json", *INPUT_OPTIONS, str(path),
        ],
        timeout=20,
    )
    if proc.returncode != 0:
        raise KettuError(ErrorCode.UNSUPPORTED_FILE)
    data = json.loads(proc.stdout or b"{}")
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    try:
        duration = float(data.get("format", {}).get("duration") or 0.0)
    except ValueError:
        duration = 0.0
    return ProbeInfo(duration_s=duration, has_audio=bool(audio), codec=audio[0].get("codec_name") if audio else None)


async def check_upload(path: Path, max_seconds: float, max_mb: float) -> ProbeInfo:
    """Refuse bad input before any paid call."""
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise KettuError(ErrorCode.TOO_BIG)
    info = await probe(path)
    if not info.has_audio:
        raise KettuError(ErrorCode.UNSUPPORTED_FILE)
    if not math.isfinite(info.duration_s) or info.duration_s < 0:
        raise KettuError(ErrorCode.UNSUPPORTED_FILE)
    if info.duration_s > max_seconds + 1:
        raise KettuError(ErrorCode.TOO_LONG)
    return info


async def clean(src: Path, dst: Path, max_seconds: float = 180.0) -> float:
    """Any input → 16 kHz mono 16-bit WAV, silence trimmed at both ends, loudness normalised.

    Returns the cleaned duration in seconds (what Prisma will bill).
    """
    trim = f"silenceremove=start_periods=1:start_threshold={SILENCE_DB - 10}dB:start_silence=0.25"
    afilter = f"{trim},areverse,{trim},areverse,dynaudnorm=f=150:g=15"
    proc = await run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *INPUT_OPTIONS,
         "-t", str(max_seconds + 2), "-i", str(src),
         "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-af", afilter, "-c:a", "pcm_s16le", str(dst)],
        timeout=120,
    )
    if proc.returncode != 0 or not dst.exists():
        log.warning("ffmpeg clean failed rc=%s", proc.returncode)
        raise KettuError(ErrorCode.UNSUPPORTED_FILE)
    duration = wav_duration(dst)
    if duration < 0.3:
        raise KettuError(ErrorCode.NO_SPEECH)
    return duration


def wav_duration(path: Path) -> float:
    """Timbre streams WAVs with a 0xFFFFFFFF size placeholder, so never trust the header beyond the file size."""
    with wave.open(str(path), "rb") as w:
        bytes_per_frame = w.getsampwidth() * w.getnchannels()
        frames_in_file = max(0, path.stat().st_size - 44) // max(1, bytes_per_frame)
        return min(w.getnframes(), frames_in_file) / float(w.getframerate())


async def detect_silences(path: Path) -> list[tuple[float, float]]:
    proc = await run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-af", f"silencedetect=noise={SILENCE_DB}dB:d={SILENCE_MIN_S}", "-f", "null", "-"],
        timeout=60,
    )
    text = proc.stderr.decode("utf-8", errors="ignore")
    starts = [float(m) for m in _SILENCE_START.findall(text)]
    ends = [float(m) for m in _SILENCE_END.findall(text)]
    return list(zip(starts, ends))


def plan_cuts(duration: float, silences: list[tuple[float, float]], max_chunk: float) -> list[tuple[float, float]]:
    """Cut at the middle of the latest pause that keeps each chunk under max_chunk; hard cut if none."""
    mids = sorted((s + e) / 2 for s, e in silences if e > s)
    chunks: list[tuple[float, float]] = []
    start = 0.0
    while duration - start > max_chunk:
        limit = start + max_chunk
        candidates = [m for m in mids if start + MIN_CHUNK_S <= m <= limit]
        cut = candidates[-1] if candidates else limit
        chunks.append((start, cut))
        start = cut
    if duration - start > 0.05 or not chunks:
        chunks.append((start, duration))
    return chunks


def slice_wav(src: Path, start: float, end: float, dst: Path) -> None:
    with wave.open(str(src), "rb") as r:
        rate = r.getframerate()
        r.setpos(int(start * rate))
        frames = r.readframes(max(0, int((end - start) * rate)))
        params = r.getparams()
    with wave.open(str(dst), "wb") as w:
        w.setparams(params)
        w.writeframes(frames)


async def split(wav: Path, out_dir: Path, max_chunk: float) -> list[tuple[Path, float]]:
    """Split a cleaned WAV into chunks at pauses. Returns (path, seconds) pairs in order."""
    duration = wav_duration(wav)
    silences = await detect_silences(wav) if duration > max_chunk else []
    parts = []
    for i, (s, e) in enumerate(plan_cuts(duration, silences, max_chunk)):
        dst = out_dir / f"chunk_{i:02d}.wav"
        await asyncio.to_thread(slice_wav, wav, s, e, dst)
        parts.append((dst, e - s))
    return parts


async def encode_reply(wav_bytes: bytes, fmt: str, work: Path) -> bytes:
    """Timbre WAV → MP3 (plays everywhere) or OGG/Opus (WhatsApp voice-note bubble)."""
    src = work / "reply_src.wav"
    src.write_bytes(wav_bytes)
    if fmt == "ogg":
        dst = work / "reply.ogg"
        codec = ["-c:a", "libopus", "-b:a", "32k", "-application", "voip", "-ar", "48000"]
    else:
        dst = work / "reply.mp3"
        codec = ["-c:a", "libmp3lame", "-b:a", "64k", "-ar", "24000"]
    proc = await run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-ac", "1", *codec, str(dst)],
        timeout=60,
    )
    if proc.returncode != 0 or not dst.exists():
        raise KettuError(ErrorCode.INTERNAL, "Could not make the voice note audio.")
    return dst.read_bytes()


def tone_wav(seconds: float = 1.5, freq: float = 440.0, rate: int = 24000) -> bytes:
    """A short beep as WAV bytes; stands in for Timbre in mock mode."""
    import io

    buf = io.BytesIO()
    n = int(seconds * rate)
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        fade = int(0.05 * rate)
        frames = bytearray()
        for i in range(n):
            amp = min(1.0, i / fade, (n - i) / fade) * 0.3
            frames += struct.pack("<h", int(amp * 32767 * math.sin(2 * math.pi * freq * i / rate)))
        w.writeframes(bytes(frames))
    return buf.getvalue()
