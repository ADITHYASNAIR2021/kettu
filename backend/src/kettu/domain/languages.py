"""The ten Indian languages Prisma and Timbre both support."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str  # Gnani code, e.g. "ml-IN"
    name: str  # English name
    native: str  # name in its own script
    v25_female: str  # Timbre v2.5 fallback voices (v3.0 voices speak every language)
    v25_male: str


LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("ml-IN", "Malayalam", "മലയാളം", "Reshma", "Riyaan"),
        Language("hi-IN", "Hindi", "हिन्दी", "Nalini", "Deepak"),
        Language("bn-IN", "Bengali", "বাংলা", "Kirra", "Dhruva"),
        Language("ta-IN", "Tamil", "தமிழ்", "Asmita", "Asmita"),
        Language("te-IN", "Telugu", "తెలుగు", "Lavanya", "Lavanya"),
        Language("kn-IN", "Kannada", "ಕನ್ನಡ", "Saanvi", "Kavin"),
        Language("mr-IN", "Marathi", "मराठी", "Zahira", "Ishaan"),
        Language("gu-IN", "Gujarati", "ગુજરાતી", "Falak", "Veera"),
        Language("pa-IN", "Punjabi", "ਪੰਜਾਬੀ", "Mehuli", "Zayan"),
        Language("en-IN", "English", "English", "Kaveri", "Pranav"),
    ]
}

DEFAULT_LANG = "ml-IN"


def is_supported(code: str | None) -> bool:
    return bool(code) and code in LANGUAGES


def get(code: str) -> Language:
    return LANGUAGES.get(code) or LANGUAGES["en-IN"]


def name(code: str | None) -> str:
    return get(code).name if code else "Unknown"


def same_language(a: str | None, b: str | None) -> bool:
    """Prisma may return a code we do not list (e.g. "en-US"); compare on the language part."""
    if not a or not b:
        return False
    return a.split("-")[0].lower() == b.split("-")[0].lower()


def normalise(code: str | None) -> str | None:
    """Map whatever Prisma reports onto one of our ten codes, or None."""
    if not code:
        return None
    if code in LANGUAGES:
        return code
    base = code.split("-")[0].lower()
    for known in LANGUAGES:
        if known.startswith(base + "-"):
            return known
    return None
