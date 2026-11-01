"""Prompts and JSON schemas for the two LLM calls (understand a note, draft a reply)."""

import json

UNDERSTAND_SYSTEM = """You help people understand WhatsApp voice notes in Indian languages.
You get a transcript from speech recognition. It can contain recognition mistakes, English words in Latin script, and several languages mixed together.

Return only JSON that matches the schema.
- translation: a faithful translation into {my_lang_name}, in its native script. Keep names, places and brand names as spoken. Do not add facts. Write [unclear] for words you cannot make sense of. Empty string if want_translation is false.
- gist: only if want_gist is true, at most two short sentences in {my_lang_name}. Otherwise an empty string.
- entities: every time, date, money amount, quantity, person name and place, with its value written in {my_lang_name} and the exact source_text copied from the transcript. Empty list if there are none.
- order_items: only if mode is "orders": each item with quantity and unit, item names in {my_lang_name}. Otherwise an empty list.
Never give medical, legal or financial advice. Only describe what the speaker said."""

REPLY_SYSTEM = """Translate the user's reply from {from_lang_name} into {to_lang_name} for a voice note that will be spoken aloud.
- Keep it short and natural, the way a person says it on the phone.
- Write numbers, times, dates and money as spoken words in {to_lang_name}.
- Keep names unchanged.
- Write {to_lang_name} in its native script.
Then translate your output back into {from_lang_name} word for word, so the sender can check the meaning.
Return only JSON: {{"target_text": "...", "back_translation": "..."}}"""

UNDERSTAND_SCHEMA = {
    "type": "object",
    "properties": {
        "translation": {"type": "string"},
        "gist": {"type": "string"},
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["time", "date", "amount", "quantity", "name", "place"]},
                    "value": {"type": "string"},
                    "source_text": {"type": "string"},
                },
                "required": ["type", "value", "source_text"],
                "additionalProperties": False,
            },
        },
        "order_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item": {"type": "string"},
                    "quantity": {"type": "string"},
                    "unit": {"type": "string"},
                },
                "required": ["item", "quantity", "unit"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["translation", "gist", "entities", "order_items"],
    "additionalProperties": False,
}

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "target_text": {"type": "string"},
        "back_translation": {"type": "string"},
    },
    "required": ["target_text", "back_translation"],
    "additionalProperties": False,
}


def understand_user_message(
    source_lang: str | None, duration_s: float, want_gist: bool, want_translation: bool, mode: str, transcript: str
) -> str:
    return json.dumps(
        {
            "source_lang": source_lang or "unknown",
            "duration_s": round(duration_s, 1),
            "want_gist": want_gist,
            "want_translation": want_translation,
            "mode": mode,
            "transcript": transcript,
        },
        ensure_ascii=False,
    )
