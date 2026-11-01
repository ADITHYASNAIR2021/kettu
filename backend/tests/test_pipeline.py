from kettu.domain.models import ReplyDraft, Understanding
from kettu.services.gnani import MockSpeech
from kettu.services.llm import MockLLM
from kettu.services.pipeline import Pipeline


class RecordingSpeech(MockSpeech):
    def __init__(self, lang="bn-IN"):
        self.calls = []
        self.lang = lang

    async def transcribe(self, wav, language_code, previous_text="", keyterms=None):
        self.calls.append({"language_code": language_code, "previous_text": previous_text, "keyterms": keyterms})
        return f"part{len(self.calls)}", self.lang


class RecordingLLM(MockLLM):
    def __init__(self):
        self.understand_calls = []
        self.reply_calls = []

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode):
        self.understand_calls.append(dict(want_gist=want_gist, want_translation=want_translation, mode=mode))
        return Understanding(translation="T" if want_translation else None, gist="G" if want_gist else None), 42

    async def reply(self, text, from_lang, to_lang):
        self.reply_calls.append((text, from_lang, to_lang))
        return ReplyDraft(target_text="X", back_translation="Y"), 7


async def test_long_note_is_chunked_with_context_and_gets_a_gist(settings, long_note):
    speech, llm = RecordingSpeech(), RecordingLLM()
    result, usage = await Pipeline(settings, speech, llm).understand_note(long_note, "ml-IN", keyterms=["Rakib"])
    assert len(speech.calls) >= 3
    assert speech.calls[0]["language_code"] == "indic-auto"
    assert speech.calls[0]["previous_text"] == ""
    assert speech.calls[1]["previous_text"] == "part1"
    assert speech.calls[0]["keyterms"] == ["Rakib"]
    assert llm.understand_calls == [dict(want_gist=True, want_translation=True, mode="listen")]
    assert result.detected_lang == "bn-IN"
    assert result.translation == "T" and result.gist == "G"
    assert result.transcript.startswith("part1 part2")
    assert usage.llm_tokens == 42 and usage.stt_seconds > 60


async def test_short_note_in_my_language_skips_the_llm(settings, short_note):
    speech, llm = RecordingSpeech(lang="ml-IN"), RecordingLLM()
    result, _ = await Pipeline(settings, speech, llm).understand_note(short_note, "ml-IN")
    assert llm.understand_calls == []
    assert result.same_language and result.translation is None and result.gist is None


async def test_hint_languages_are_passed_to_prisma(settings, short_note):
    speech, llm = RecordingSpeech(), RecordingLLM()
    await Pipeline(settings, speech, llm).understand_note(short_note, "ml-IN", hint_langs=["bn-IN", "hi-IN", "xx"])
    assert speech.calls[0]["language_code"] == "bn-IN,hi-IN"


async def test_orders_mode_reaches_the_llm(settings, short_note):
    speech, llm = RecordingSpeech(lang="ml-IN"), RecordingLLM()
    await Pipeline(settings, speech, llm).understand_note(short_note, "ml-IN", mode="orders")
    assert llm.understand_calls[0]["mode"] == "orders"


async def test_reply_preview_text_and_same_language(settings):
    llm = RecordingLLM()
    p = Pipeline(settings, RecordingSpeech(), llm)
    draft, src, _ = await p.preview_reply("ml-IN", "bn-IN", text="നാളെ വരണം")
    assert (draft.target_text, draft.back_translation, src) == ("X", "Y", "നാളെ വരണം")
    draft, _, _ = await p.preview_reply("ml-IN", "ml-IN", text="same")
    assert draft.target_text == "same" and len(llm.reply_calls) == 1


async def test_spoken_reply_is_transcribed_in_my_language(settings, short_note):
    speech = RecordingSpeech(lang="ml-IN")
    p = Pipeline(settings, speech, RecordingLLM())
    _, src, usage = await p.preview_reply("ml-IN", "bn-IN", audio_path=short_note)
    assert speech.calls[0]["language_code"] == "ml-IN"
    assert src == "part1" and usage.stt_seconds > 5


async def test_speak_reply_returns_ogg(settings):
    p = Pipeline(settings, MockSpeech(), MockLLM())
    data, usage = await p.speak_reply("হ্যাঁ, কাল আসব।", "bn-IN", "female", "ogg")
    assert data[:4] == b"OggS" and usage.tts_chars == len("হ্যাঁ, কাল আসব।")
