import pytest

from kettu.domain.errors import ErrorCode, KettuError
from kettu.services import audio


def test_plan_cuts_prefers_pauses():
    silences = [(9.0, 10.0), (19.0, 20.0), (29.0, 30.0), (39.0, 40.0)]
    chunks = audio.plan_cuts(45.0, silences, 28.0)
    assert chunks[0] == (0.0, 19.5)
    assert all(e - s <= 28.0 for s, e in chunks)
    assert chunks[-1][1] == 45.0


def test_plan_cuts_hard_cut_without_pauses():
    chunks = audio.plan_cuts(70.0, [], 28.0)
    assert chunks == [(0.0, 28.0), (28.0, 56.0), (56.0, 70.0)]


def test_plan_cuts_short_note_is_one_chunk():
    assert audio.plan_cuts(12.0, [], 28.0) == [(0.0, 12.0)]


async def test_clean_and_split_long_note(long_note, tmp_path):
    info = await audio.check_upload(long_note, 180, 10)
    assert 68 < info.duration_s < 71
    wav = tmp_path / "clean.wav"
    duration = await audio.clean(long_note, wav)
    assert 60 < duration < 71
    parts = await audio.split(wav, tmp_path, 28.0)
    assert len(parts) >= 3
    assert all(secs <= 28.0 + 0.01 for _, secs in parts)
    assert abs(sum(secs for _, secs in parts) - duration) < 0.1


async def test_check_upload_refuses_non_audio(tmp_path):
    bad = tmp_path / "note.ogg"
    bad.write_text("not audio at all")
    with pytest.raises(KettuError) as e:
        await audio.check_upload(bad, 180, 10)
    assert e.value.code == ErrorCode.UNSUPPORTED_FILE


async def test_check_upload_refuses_long_notes(long_note):
    with pytest.raises(KettuError) as e:
        await audio.check_upload(long_note, 60, 10)
    assert e.value.code == ErrorCode.TOO_LONG


async def test_silence_only_is_no_speech(tmp_path):
    from tests.conftest import make_tone_file

    quiet = make_tone_file(tmp_path / "quiet.ogg", [("silence", 3.0)])
    with pytest.raises(KettuError) as e:
        await audio.clean(quiet, tmp_path / "c.wav")
    assert e.value.code == ErrorCode.NO_SPEECH


@pytest.mark.parametrize("fmt,magic", [("ogg", b"OggS"), ("mp3", None)])
async def test_encode_reply(tmp_path, fmt, magic):
    out = await audio.encode_reply(audio.tone_wav(1.0), fmt, tmp_path)
    assert len(out) > 500
    if magic:
        assert out[:4] == magic
    else:
        assert out[:3] == b"ID3" or out[0] == 0xFF
