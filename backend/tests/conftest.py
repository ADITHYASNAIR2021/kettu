import subprocess
from pathlib import Path

import pytest

from kettu.config import Settings


def make_tone_file(path: Path, pattern: list[tuple[str, float]]) -> Path:
    """Build an audio file from ("tone"|"silence", seconds) parts, e.g. a fake 70 s voice note with pauses."""
    inputs, labels = [], []
    for i, (kind, secs) in enumerate(pattern):
        src = f"sine=frequency=300:duration={secs}" if kind == "tone" else f"anullsrc=r=16000:cl=mono:d={secs}"
        inputs += ["-f", "lavfi", "-i", src]
        labels.append(f"[{i}:a]")
    graph = "".join(labels) + f"concat=n={len(pattern)}:v=0:a=1[out]"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *inputs, "-filter_complex", graph,
         "-map", "[out]", "-ac", "1", "-ar", "16000", "-c:a", "libopus", "-b:a", "24k", str(path)],
        check=True,
    )
    return path


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        speech_provider="mock",
        llm_provider="mock",
        cors_origins="http://localhost:3000",
        notes_per_day=3,
        replies_per_day=2,
        work_dir=str(tmp_path),
        wa_access_token="test-token",
        wa_phone_number_id="123",
        wa_app_secret="secret",
        wa_verify_token="verify-me",
        wa_hash_salt="salt",
    )


@pytest.fixture
def short_note(tmp_path) -> Path:
    return make_tone_file(tmp_path / "short.ogg", [("tone", 4.0), ("silence", 0.6), ("tone", 3.0)])


@pytest.fixture
def long_note(tmp_path) -> Path:
    pattern = []
    for _ in range(7):  # 7 x (9 s speech + 1 s pause) = 70 s
        pattern += [("tone", 9.0), ("silence", 1.0)]
    return make_tone_file(tmp_path / "long.ogg", pattern[:-1])
