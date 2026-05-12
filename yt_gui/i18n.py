from .locales import en, ja

_LANGUAGES: dict[str, dict[str, str]] = {
    "ja": ja.STRINGS,
    "en": en.STRINGS,
}

AVAILABLE_LANGUAGES: list[str] = list(_LANGUAGES.keys())

_current_lang = "ja"


def set_language(lang: str) -> None:
    global _current_lang
    if lang in _LANGUAGES:
        _current_lang = lang


def t(key: str) -> str:
    val = _LANGUAGES.get(_current_lang, {}).get(key)
    if val is not None:
        return val
    return _LANGUAGES.get("ja", {}).get(key, key)
