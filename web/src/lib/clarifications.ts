import type { LangCode } from "./languages";

export type Clarification = "date" | "quantity" | "repeat";

/** Drafts are in the reader's language, matching the reply translator's declared source language. */
export const CLARIFICATIONS: Record<LangCode, Record<Clarification, string>> = {
  "en-IN": {
    date: "Please confirm the date and time.",
    quantity: "Please confirm the quantity.",
    repeat: "Could you please say that again?",
  },
  "ml-IN": {
    date: "ദയവായി തീയതിയും സമയവും ഉറപ്പാക്കി പറയാമോ?",
    quantity: "ദയവായി അളവ് ഉറപ്പാക്കി പറയാമോ?",
    repeat: "ദയവായി അത് ഒന്നുകൂടി പറയാമോ?",
  },
  "hi-IN": {
    date: "कृपया तारीख और समय की पुष्टि करें।",
    quantity: "कृपया मात्रा की पुष्टि करें।",
    repeat: "क्या आप कृपया वह बात फिर से कह सकते हैं?",
  },
  "bn-IN": {
    date: "দয়া করে তারিখ আর সময় নিশ্চিত করে বলবেন?",
    quantity: "দয়া করে পরিমাণটা নিশ্চিত করে বলবেন?",
    repeat: "দয়া করে কথাটা আর একবার বলবেন?",
  },
  "ta-IN": {
    date: "தயவுசெய்து தேதியையும் நேரத்தையும் உறுதிப்படுத்துங்கள்.",
    quantity: "தயவுசெய்து அளவை உறுதிப்படுத்துங்கள்.",
    repeat: "தயவுசெய்து அதை மீண்டும் சொல்ல முடியுமா?",
  },
  "te-IN": {
    date: "దయచేసి తేదీ మరియు సమయాన్ని నిర్ధారించండి.",
    quantity: "దయచేసి పరిమాణాన్ని నిర్ధారించండి.",
    repeat: "దయచేసి అది మళ్ళీ చెప్పగలరా?",
  },
  "kn-IN": {
    date: "ದಯವಿಟ್ಟು ದಿನಾಂಕ ಮತ್ತು ಸಮಯವನ್ನು ಖಚಿತಪಡಿಸಿ.",
    quantity: "ದಯವಿಟ್ಟು ಪ್ರಮಾಣವನ್ನು ಖಚಿತಪಡಿಸಿ.",
    repeat: "ದಯವಿಟ್ಟು ಅದನ್ನು ಮತ್ತೊಮ್ಮೆ ಹೇಳಬಹುದೇ?",
  },
  "mr-IN": {
    date: "कृपया तारीख आणि वेळ नक्की करून सांगा.",
    quantity: "कृपया प्रमाण नक्की करून सांगा.",
    repeat: "कृपया ते पुन्हा सांगू शकाल का?",
  },
  "gu-IN": {
    date: "કૃપા કરીને તારીખ અને સમયની ખાતરી કરો.",
    quantity: "કૃપા કરીને જથ્થાની ખાતરી કરો.",
    repeat: "કૃપા કરીને તે ફરીથી કહી શકશો?",
  },
  "pa-IN": {
    date: "ਕਿਰਪਾ ਕਰਕੇ ਤਾਰੀਖ ਅਤੇ ਸਮੇਂ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ।",
    quantity: "ਕਿਰਪਾ ਕਰਕੇ ਮਾਤਰਾ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ।",
    repeat: "ਕੀ ਤੁਸੀਂ ਕਿਰਪਾ ਕਰਕੇ ਉਹ ਗੱਲ ਦੁਬਾਰਾ ਕਹਿ ਸਕਦੇ ਹੋ?",
  },
};
