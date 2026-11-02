import type { CardAction, CardField } from "./cards";
import type { LangCode } from "./languages";

export const CONFIRM_LABELS: Record<LangCode, { intro: string; task: string; quantity: string; person: string; deadline: string }> = {
  "en-IN": { intro: "Please confirm these details:", task: "Task", quantity: "Quantity", person: "Person", deadline: "When" },
  "ml-IN": { intro: "ദയവായി ഈ വിവരങ്ങൾ ഉറപ്പാക്കി പറയാമോ?", task: "ജോലി", quantity: "അളവ്", person: "ആൾ", deadline: "എപ്പോൾ" },
  "hi-IN": { intro: "कृपया इन बातों की पुष्टि करें:", task: "काम", quantity: "मात्रा", person: "व्यक्ति", deadline: "कब" },
  "bn-IN": { intro: "দয়া করে এই তথ্যগুলো নিশ্চিত করুন:", task: "কাজ", quantity: "পরিমাণ", person: "ব্যক্তি", deadline: "কখন" },
  "ta-IN": { intro: "தயவுசெய்து இந்த விவரங்களை உறுதிப்படுத்துங்கள்:", task: "பணி", quantity: "அளவு", person: "நபர்", deadline: "எப்போது" },
  "te-IN": { intro: "దయచేసి ఈ వివరాలను నిర్ధారించండి:", task: "పని", quantity: "పరిమాణం", person: "వ్యక్తి", deadline: "ఎప్పుడు" },
  "kn-IN": { intro: "ದಯವಿಟ್ಟು ಈ ವಿವರಗಳನ್ನು ಖಚಿತಪಡಿಸಿ:", task: "ಕೆಲಸ", quantity: "ಪ್ರಮಾಣ", person: "ವ್ಯಕ್ತಿ", deadline: "ಯಾವಾಗ" },
  "mr-IN": { intro: "कृपया या गोष्टींची खात्री करा:", task: "काम", quantity: "प्रमाण", person: "व्यक्ती", deadline: "कधी" },
  "gu-IN": { intro: "કૃપા કરીને આ વિગતોની ખાતરી કરો:", task: "કામ", quantity: "જથ્થો", person: "વ્યક્તિ", deadline: "ક્યારે" },
  "pa-IN": { intro: "ਕਿਰਪਾ ਕਰਕੇ ਇਨ੍ਹਾਂ ਵੇਰਵਿਆਂ ਦੀ ਪੁਸ਼ਟੀ ਕਰੋ:", task: "ਕੰਮ", quantity: "ਮਾਤਰਾ", person: "ਵਿਅਕਤੀ", deadline: "ਕਦੋਂ" },
};

export function confirmationText(actions: CardAction[], fields: Record<string, CardField[]>, language: LangCode): string {
  const labels = CONFIRM_LABELS[language];
  const blocks = actions.map((action) => (fields[action.id] ?? [])
    .filter((field) => action[field].trim()).map((field) => `${labels[field]}: ${action[field]}`).join("\n")).filter(Boolean);
  return blocks.length ? `${labels.intro}\n\n${blocks.join("\n\n")}` : "";
}
