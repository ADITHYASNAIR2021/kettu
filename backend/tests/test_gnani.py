import httpx
import pytest

from kettu.domain.errors import KettuError
from kettu.services.audio import tone_wav
from kettu.services.gnani import GnaniSpeech, plausible_seconds, wav_seconds

TEXT = "হ্যাঁ, কাল সকাল আটটায় আসব। গেট খোলা থাকবে।"


def streaming_header(wav: bytes) -> bytes:
    """Mimic Timbre: data-size fields set to 0xFFFFFFFF."""
    b = bytearray(wav)
    b[4:8] = b"\xff\xff\xff\xff"
    b[40:44] = b"\xff\xff\xff\xff"
    return bytes(b)


def speech_with(handler, settings) -> GnaniSpeech:
    client = httpx.AsyncClient(base_url="https://api.vachana.ai", transport=httpx.MockTransport(handler))
    return GnaniSpeech(settings, client=client)


def test_wav_seconds_ignores_bogus_header():
    assert abs(wav_seconds(streaming_header(tone_wav(3.0))) - 3.0) < 0.05
    assert plausible_seconds(TEXT) >= 6.0


async def test_run_on_audio_is_retried(settings):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        secs = 20.0 if len(calls) == 1 else 3.2  # first answer keeps talking for 20 s
        return httpx.Response(200, content=streaming_header(tone_wav(secs)), headers={"content-type": "audio/wav"})

    wav = await speech_with(handler, settings).synthesize(TEXT, "bn-IN", "male")
    assert len(calls) == 2 and abs(wav_seconds(wav) - 3.2) < 0.05


async def test_rejected_model_falls_back_to_v25_voices(settings):
    seen = []

    def handler(request: httpx.Request):
        import json

        body = json.loads(request.content)
        seen.append((body["model"], body["voice"]))
        if body["model"] == "timbre-v3.0":
            return httpx.Response(400, json={"success": False, "message": "invalid model"})
        return httpx.Response(200, content=tone_wav(2.0))

    speech = speech_with(handler, settings)
    await speech.synthesize(TEXT, "bn-IN", "male")
    assert seen == [("timbre-v3.0", "Avinash"), ("timbre-v2.5", "Dhruva")]
    await speech.synthesize(TEXT, "ml-IN", "female")  # sticks to the model that works
    assert seen[-1] == ("timbre-v2.5", "Reshma")


async def test_always_running_on_is_an_error(settings):
    def handler(request):
        return httpx.Response(200, content=tone_wav(30.0))

    with pytest.raises(KettuError):
        await speech_with(handler, settings).synthesize("ok", "hi-IN", "female")
