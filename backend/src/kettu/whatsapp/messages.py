"""Bot texts in English, Malayalam, Hindi and Bengali. Other languages fall back to English."""

from kettu.domain import languages
from kettu.domain.models import NoteResult

T: dict[str, dict[str, str]] = {
    "en": {
        "welcome": "Hi! I'm *Kettu* 👂 (Malayalam for \"heard\").\n\nForward a voice note to read it in your language and reply with an AI voice in theirs.\n\nAudio goes to Gnani AI; text goes to Gemini or Anthropic. This takes the note outside WhatsApp's encrypted chat. Use fictional details for this demo; only forward notes you have permission to share. Check the translation before acting on it.\n\nFirst, which language do you read?",
        "pick_body": "Choose the language you want notes translated into.",
        "pick_button": "Choose language",
        "pick_section": "Languages",
        "lang_set": "✅ Got it: {lang}.\n\nNow forward me a voice note. Type *help* any time.",
        "help": "*How to use Kettu*\n1. In any chat, long-press a voice note → Forward → *Kettu*.\n2. I send back the text in {lang}.\n3. Tap *Reply in …*, then send me your answer (voice or text) in {lang}. I turn it into a voice note in their language. Forward that back to them.\n\nCommands: *language* · *voice* · *orders* · *cancel*\nToday: {notes} notes and {replies} voice replies left.",
        "queued": "⏳ Got it. {n} note(s) ahead of yours.",
        "listening": "🎧 Listening…",
        "gist": "Gist",
        "in_lang": "In {lang}",
        "original": "Original ({lang})",
        "already": "Already in {lang}",
        "order": "Order list",
        "reply_q": "Want to answer in {lang}?",
        "reply_btn": "Reply in {lang}",
        "prompt_reply": "🎙️ Send your reply in *{mine}*, as a voice note or text. I'll turn it into a {theirs} voice note.\n\nType *cancel* to stop.",
        "drafting": "✍️ Translating your reply…",
        "preview": "*{theirs}:*\n{target}\n\n_Meaning, back in {mine}:_\n{back}",
        "preview_q": "Make this into a voice note?",
        "btn_speak": "🔊 Make voice note",
        "btn_retry": "✏️ Change it",
        "btn_cancel": "Cancel",
        "speaking": "🔊 Making the voice note…",
        "forward_hint": "↪️ Long-press the voice note above → Forward → pick the chat.\n_Translated by Kettu (AI voice)._",
        "cancelled": "OK, cancelled.",
        "thanks_up": "Thanks! 🙏",
        "reason_q": "Sorry about that. What went wrong?",
        "r_lang": "Wrong language",
        "r_words": "Wrong words",
        "r_trans": "Bad translation",
        "thanks_down": "Thanks, that helps us fix it.",
        "orders_on": "🛒 Your next voice note will be read as an order list.",
        "voice_q": "Which voice should your replies use?",
        "female": "Female voice",
        "male": "Male voice",
        "voice_set": "✅ Replies will use the {voice}.",
        "expired": "That reply has expired. Tap *Reply* on a note again.",
        "not_audio": "Send me a voice note, or type *help*.",
        "no_reply_target": "Forward me a voice note first, then tap *Reply*.",
        "error": "⚠️ {message}",
    },
    "ml": {
        "lang_set": "✅ ശരി: {lang}.\n\nഇനി ഒരു വോയ്സ് നോട്ട് ഫോർവേഡ് ചെയ്യൂ. സഹായത്തിന് *help* എന്ന് ടൈപ്പ് ചെയ്യൂ.",
        "help": "*കേട്ടു എങ്ങനെ ഉപയോഗിക്കാം*\n1. ഏത് ചാറ്റിലും വോയ്സ് നോട്ട് ലോങ്-പ്രസ് ചെയ്ത് → Forward → *Kettu*.\n2. അത് {lang}-ൽ എഴുതി തിരിച്ചയക്കും.\n3. *മറുപടി* ടാപ്പ് ചെയ്ത് നിങ്ങളുടെ ഉത്തരം {lang}-ൽ (വോയ്സ് അല്ലെങ്കിൽ ടെക്സ്റ്റ്) അയക്കൂ. അവരുടെ ഭാഷയിൽ വോയ്സ് നോട്ട് ഉണ്ടാക്കിത്തരാം.\n\nകമാൻഡുകൾ: *language* · *voice* · *orders* · *cancel*\nഇന്ന് ബാക്കി: {notes} നോട്ടുകൾ, {replies} വോയ്സ് മറുപടികൾ.",
        "queued": "⏳ കിട്ടി. നിങ്ങൾക്ക് മുമ്പ് {n} നോട്ട്(കൾ) ഉണ്ട്.",
        "listening": "🎧 കേൾക്കുന്നു…",
        "gist": "ചുരുക്കം",
        "in_lang": "{lang}-ൽ",
        "original": "യഥാർത്ഥം ({lang})",
        "already": "ഇത് ഇതിനകം {lang}-ൽ ആണ്",
        "order": "ഓർഡർ ലിസ്റ്റ്",
        "reply_q": "{lang}-ൽ മറുപടി അയക്കണോ?",
        "reply_btn": "{lang}-ൽ മറുപടി",
        "prompt_reply": "🎙️ നിങ്ങളുടെ മറുപടി *{mine}*-ൽ വോയ്സ് ആയോ ടെക്സ്റ്റ് ആയോ അയക്കൂ. അത് {theirs} വോയ്സ് നോട്ട് ആക്കിത്തരാം.\n\nനിർത്താൻ *cancel* ടൈപ്പ് ചെയ്യൂ.",
        "drafting": "✍️ മറുപടി വിവർത്തനം ചെയ്യുന്നു…",
        "preview": "*{theirs}:*\n{target}\n\n_അർത്ഥം, {mine}-ൽ:_\n{back}",
        "preview_q": "ഇത് വോയ്സ് നോട്ട് ആക്കണോ?",
        "btn_speak": "🔊 വോയ്സ് നോട്ട്",
        "btn_retry": "✏️ മാറ്റുക",
        "btn_cancel": "റദ്ദാക്കുക",
        "speaking": "🔊 വോയ്സ് നോട്ട് ഉണ്ടാക്കുന്നു…",
        "forward_hint": "↪️ മുകളിലെ വോയ്സ് നോട്ട് ലോങ്-പ്രസ് → Forward → ചാറ്റ് തിരഞ്ഞെടുക്കൂ.\n_Kettu വിവർത്തനം ചെയ്തത് (AI ശബ്ദം)._",
        "cancelled": "ശരി, റദ്ദാക്കി.",
        "thanks_up": "നന്ദി! 🙏",
        "reason_q": "ക്ഷമിക്കണം. എന്താണ് തെറ്റിയത്?",
        "r_lang": "ഭാഷ തെറ്റി",
        "r_words": "വാക്കുകൾ തെറ്റി",
        "r_trans": "വിവർത്തനം മോശം",
        "thanks_down": "നന്ദി, ഇത് ശരിയാക്കാൻ സഹായിക്കും.",
        "orders_on": "🛒 അടുത്ത വോയ്സ് നോട്ട് ഓർഡർ ലിസ്റ്റ് ആയി വായിക്കും.",
        "voice_q": "മറുപടികൾക്ക് ഏത് ശബ്ദം വേണം?",
        "female": "സ്ത്രീ ശബ്ദം",
        "male": "പുരുഷ ശബ്ദം",
        "voice_set": "✅ മറുപടികൾ {voice}-ൽ ആയിരിക്കും.",
        "expired": "ആ മറുപടിയുടെ സമയം കഴിഞ്ഞു. ഒരു നോട്ടിൽ വീണ്ടും *മറുപടി* ടാപ്പ് ചെയ്യൂ.",
        "not_audio": "ഒരു വോയ്സ് നോട്ട് അയക്കൂ, അല്ലെങ്കിൽ *help* ടൈപ്പ് ചെയ്യൂ.",
        "no_reply_target": "ആദ്യം ഒരു വോയ്സ് നോട്ട് ഫോർവേഡ് ചെയ്യൂ, പിന്നെ *മറുപടി* ടാപ്പ് ചെയ്യൂ.",
    },
    "hi": {
        "lang_set": "✅ ठीक है: {lang}.\n\nअब कोई वॉइस नोट फ़ॉरवर्ड करें। मदद के लिए *help* लिखें।",
        "help": "*केट्टु कैसे इस्तेमाल करें*\n1. किसी भी चैट में वॉइस नोट पर लंबा दबाएँ → Forward → *Kettu*.\n2. मैं उसे {lang} में लिखकर भेजूँगा।\n3. *जवाब* दबाएँ, फिर अपना जवाब {lang} में (आवाज़ या टेक्स्ट) भेजें। मैं उसे उनकी भाषा में वॉइस नोट बना दूँगा।\n\nकमांड: *language* · *voice* · *orders* · *cancel*\nआज बाकी: {notes} नोट, {replies} वॉइस जवाब।",
        "queued": "⏳ मिल गया। आपसे पहले {n} नोट हैं।",
        "listening": "🎧 सुन रहा हूँ…",
        "gist": "सार",
        "in_lang": "{lang} में",
        "original": "मूल ({lang})",
        "already": "यह पहले से {lang} में है",
        "order": "ऑर्डर सूची",
        "reply_q": "{lang} में जवाब देना है?",
        "reply_btn": "{lang} में जवाब",
        "prompt_reply": "🎙️ अपना जवाब *{mine}* में भेजें, आवाज़ या टेक्स्ट में। मैं उसे {theirs} वॉइस नोट बना दूँगा।\n\nरोकने के लिए *cancel* लिखें।",
        "drafting": "✍️ जवाब का अनुवाद हो रहा है…",
        "preview": "*{theirs}:*\n{target}\n\n_मतलब, {mine} में:_\n{back}",
        "preview_q": "इसे वॉइस नोट बनाएँ?",
        "btn_speak": "🔊 वॉइस नोट बनाएँ",
        "btn_retry": "✏️ बदलें",
        "btn_cancel": "रद्द करें",
        "speaking": "🔊 वॉइस नोट बन रहा है…",
        "forward_hint": "↪️ ऊपर वाले वॉइस नोट पर लंबा दबाएँ → Forward → चैट चुनें।\n_Kettu द्वारा अनुवादित (AI आवाज़)._",
        "cancelled": "ठीक है, रद्द कर दिया।",
        "thanks_up": "धन्यवाद! 🙏",
        "reason_q": "माफ़ कीजिए। क्या गलत हुआ?",
        "r_lang": "गलत भाषा",
        "r_words": "गलत शब्द",
        "r_trans": "खराब अनुवाद",
        "thanks_down": "धन्यवाद, इससे सुधारने में मदद मिलेगी।",
        "orders_on": "🛒 अगला वॉइस नोट ऑर्डर सूची की तरह पढ़ा जाएगा।",
        "voice_q": "जवाब किस आवाज़ में हों?",
        "female": "महिला आवाज़",
        "male": "पुरुष आवाज़",
        "voice_set": "✅ जवाब {voice} में होंगे।",
        "expired": "उस जवाब का समय खत्म हो गया। किसी नोट पर फिर से *जवाब* दबाएँ।",
        "not_audio": "मुझे वॉइस नोट भेजें, या *help* लिखें।",
        "no_reply_target": "पहले कोई वॉइस नोट फ़ॉरवर्ड करें, फिर *जवाब* दबाएँ।",
    },
    "bn": {
        "lang_set": "✅ ঠিক আছে: {lang}।\n\nএবার একটা ভয়েস নোট ফরওয়ার্ড করুন। সাহায্যের জন্য *help* লিখুন।",
        "help": "*কেট্টু কীভাবে ব্যবহার করবেন*\n১. যেকোনো চ্যাটে ভয়েস নোটে লম্বা চাপ দিন → Forward → *Kettu*.\n২. আমি সেটা {lang}-য় লিখে পাঠাব।\n৩. *উত্তর* চাপুন, তারপর আপনার উত্তর {lang}-য় (ভয়েস বা টেক্সট) পাঠান। আমি সেটা ওদের ভাষায় ভয়েস নোট বানিয়ে দেব।\n\nকমান্ড: *language* · *voice* · *orders* · *cancel*\nআজ বাকি: {notes}টি নোট, {replies}টি ভয়েস উত্তর।",
        "queued": "⏳ পেয়েছি। আপনার আগে {n}টি নোট আছে।",
        "listening": "🎧 শুনছি…",
        "gist": "সারাংশ",
        "in_lang": "{lang}-য়",
        "original": "মূল ({lang})",
        "already": "এটা আগেই {lang}-য় আছে",
        "order": "অর্ডারের তালিকা",
        "reply_q": "{lang}-য় উত্তর দেবেন?",
        "reply_btn": "{lang}-য় উত্তর",
        "prompt_reply": "🎙️ আপনার উত্তর *{mine}*-য় ভয়েস বা টেক্সটে পাঠান। আমি সেটা {theirs} ভয়েস নোট বানিয়ে দেব।\n\nথামাতে *cancel* লিখুন।",
        "drafting": "✍️ উত্তর অনুবাদ হচ্ছে…",
        "preview": "*{theirs}:*\n{target}\n\n_মানে, {mine}-য়:_\n{back}",
        "preview_q": "এটাকে ভয়েস নোট বানাব?",
        "btn_speak": "🔊 ভয়েস নোট বানান",
        "btn_retry": "✏️ বদলান",
        "btn_cancel": "বাতিল",
        "speaking": "🔊 ভয়েস নোট বানানো হচ্ছে…",
        "forward_hint": "↪️ ওপরের ভয়েস নোটে লম্বা চাপ দিন → Forward → চ্যাট বেছে নিন।\n_Kettu-র অনুবাদ (AI কণ্ঠ)._",
        "cancelled": "ঠিক আছে, বাতিল করা হল।",
        "thanks_up": "ধন্যবাদ! 🙏",
        "reason_q": "দুঃখিত। কী ভুল হয়েছে?",
        "r_lang": "ভুল ভাষা",
        "r_words": "ভুল শব্দ",
        "r_trans": "খারাপ অনুবাদ",
        "thanks_down": "ধন্যবাদ, এতে ঠিক করতে সাহায্য হবে।",
        "orders_on": "🛒 পরের ভয়েস নোটটা অর্ডারের তালিকা হিসেবে পড়া হবে।",
        "voice_q": "উত্তর কোন কণ্ঠে হবে?",
        "female": "মহিলা কণ্ঠ",
        "male": "পুরুষ কণ্ঠ",
        "voice_set": "✅ উত্তর {voice}-এ হবে।",
        "expired": "ওই উত্তরের সময় শেষ। কোনো নোটে আবার *উত্তর* চাপুন।",
        "not_audio": "আমাকে ভয়েস নোট পাঠান, বা *help* লিখুন।",
        "no_reply_target": "আগে একটা ভয়েস নোট ফরওয়ার্ড করুন, তারপর *উত্তর* চাপুন।",
    },
}


def ui_lang(my_lang: str | None) -> str:
    base = (my_lang or "en").split("-")[0]
    return base if base in T else "en"


def t(ui: str, key: str, **kw) -> str:
    text = T.get(ui, {}).get(key) or T["en"][key]
    return text.format(**kw) if kw else text


def lang_label(code: str | None, ui: str) -> str:
    """Native name for Indian languages (what the reader recognises), English name in the English UI."""
    if not code:
        return "?"
    lang = languages.get(code)
    return lang.name if ui == "en" else lang.native


def mmss(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def format_note(r: NoteResult, ui: str) -> str:
    src = lang_label(r.detected_lang, ui)
    mine = lang_label(r.my_lang, ui)
    lines = [f"🎧 *{src}* · {mmss(r.duration_s)}"]
    if not r.speech_live:
        lines += ["", "Demo mode: this transcript is a sample, not your recording."]
    if r.missing_facts:
        lines += ["", "⚠️ Check the original: the translation may omit " + ", ".join(r.missing_facts)]
    if r.gist:
        lines += ["", f"📝 *{t(ui, 'gist')}*", r.gist]
    if r.translation:
        lines += ["", f"🗣️ *{t(ui, 'in_lang', lang=mine)}*", r.translation]
    elif r.same_language:
        lines += ["", f"✅ _{t(ui, 'already', lang=mine)}_"]
    if r.entities:
        chips = " · ".join(dict.fromkeys(e.value for e in r.entities))
        lines += ["", f"📌 {chips}"]
    if r.order_items:
        lines += ["", f"🛒 *{t(ui, 'order')}*"]
        lines += [f"☐ {i.item} — {i.quantity} {i.unit}".rstrip() for i in r.order_items]
    lines += ["", f"_{t(ui, 'original', lang=src)}_", r.transcript]
    return "\n".join(lines)
