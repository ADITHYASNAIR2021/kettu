from kettu.domain.models import Entity, ReplyDraft, Understanding
from kettu.services.gnani import MockSpeech
from kettu.services.llm import MockLLM
from kettu.services.pipeline import Pipeline, missing_facts


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

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        self.understand_calls.append(dict(want_gist=want_gist, want_translation=want_translation, mode=mode))
        return Understanding(translation="T" if want_translation else None, gist="G" if want_gist else None), 42

    async def reply(self, text, from_lang, to_lang):
        self.reply_calls.append((text, from_lang, to_lang))
        return ReplyDraft(target_text="X", back_translation="Y"), 7


BN ="দাদা, কাল সকাল আটটায় দুটো ট্রাকে পঞ্চাশ বস্তা সিমেন্ট আসবে। রাকিবকে পাঁচশো টাকা অগ্রিম দিতে হবে।"
TRUCKS = Entity(type="quantity", value="2 trucks", source_text="দুটো ট্রাকে", in_translation="2 trucks")
BAGS = Entity(type="quantity", value="50 bags", source_text="পঞ্চাশ বস্তা", in_translation="50 bags")


class DroppingLLM(MockLLM):
    """First answer leaves the trucks out (and says it kept them); asked again with must_include, it puts them back."""

    live = True

    def __init__(self, fixes=True):
        self.fixes = fixes
        self.must = []

    async def understand(self, transcript, source_lang, my_lang, duration_s, want_gist, want_translation, mode,
                         must_include=None):
        self.must.append(must_include)
        if must_include and self.fixes:
            text = "Brother, 50 bags of cement arrive tomorrow at 8 AM in 2 trucks."
        else:
            text = "Brother, 50 bags of cement arrive tomorrow at 8 AM."
        return Understanding(translation=text, entities=[BAGS, TRUCKS]), 10


async def test_dropped_fact_triggers_one_repair(settings):
    llm = DroppingLLM()
    u, missing, tokens = await Pipeline(settings, MockSpeech(), llm).understand_text(BN, "bn-IN", "en-IN", 9, False, True)
    assert llm.must == [None, ["2 trucks (দুটো ট্রাকে)"]]
    assert "2 trucks" in u.translation and missing == [] and tokens == 20


async def test_fact_still_missing_is_reported(settings):
    llm = DroppingLLM(fixes=False)
    u, missing, _ = await Pipeline(settings, MockSpeech(), llm).understand_text(BN, "bn-IN", "en-IN", 9, False, True)
    assert len(llm.must) == 2 and missing == ["2 trucks"]


def test_fact_check_ignores_case_spacing_and_indic_digits():
    e = Entity(type="quantity", value="৫০ বস্তা", source_text="x", in_translation="৫০  Bags")
    assert missing_facts("they bring 50 bags today", [e]) == []
    assert missing_facts("they bring cement", [e]) == [e]


async def test_translate_text_to_another_language(settings):
    p = Pipeline(settings, MockSpeech(), DroppingLLM())
    out, _ = await p.translate_text(BN, "bn-IN", "hi-IN")
    assert out.to_lang == "hi-IN" and "2 trucks" in out.translation and out.translation_live
    same, tokens = await p.translate_text("নমস্কার", "bn-IN", "bn-IN")
    assert same.translation == "নমস্কার" and tokens == 0


async def test_without_a_key_the_result_says_translation_is_off(settings, short_note):
    result, _ = await Pipeline(settings, RecordingSpeech(), MockLLM()).understand_note(short_note, "ml-IN")
    assert result.translation_live is False and result.missing_facts == []


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
