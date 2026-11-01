export type LangCode =
  | "ml-IN" | "hi-IN" | "bn-IN" | "ta-IN" | "te-IN"
  | "kn-IN" | "mr-IN" | "gu-IN" | "pa-IN" | "en-IN";

export type Language = { code: LangCode; name: string; native: string };

export const LANGUAGES: Language[] = [
  { code: "ml-IN", name: "Malayalam", native: "മലയാളം" },
  { code: "hi-IN", name: "Hindi", native: "हिन्दी" },
  { code: "bn-IN", name: "Bengali", native: "বাংলা" },
  { code: "ta-IN", name: "Tamil", native: "தமிழ்" },
  { code: "te-IN", name: "Telugu", native: "తెలుగు" },
  { code: "kn-IN", name: "Kannada", native: "ಕನ್ನಡ" },
  { code: "mr-IN", name: "Marathi", native: "मराठी" },
  { code: "gu-IN", name: "Gujarati", native: "ગુજરાતી" },
  { code: "pa-IN", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { code: "en-IN", name: "English", native: "English" },
];

const BY_CODE = new Map(LANGUAGES.map((l) => [l.code, l]));

export function lang(code: string | null | undefined): Language | undefined {
  return code ? BY_CODE.get(code as LangCode) : undefined;
}

export function isLang(code: unknown): code is LangCode {
  return typeof code === "string" && BY_CODE.has(code as LangCode);
}

/** BCP-47 tag for the lang attribute, so the browser picks the right font and line breaking. */
export function htmlLang(code: string | null | undefined): string {
  return code ? code.split("-")[0] : "en";
}
