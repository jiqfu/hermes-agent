"""Internationalization (i18n) support for Hermes CLI and gateway messages.

Provides a simple _t() translation function that maps translation keys
to localized strings. DANGEROUS_PATTERNS descriptions use stable
translation keys (not English text) so that:
  1. The allowlist key never changes when locale changes
  2. The displayed description is localized for the current user

Usage:
    from hermes_cli.i18n import _t, set_locale, get_locale

    _t("patterns", "delete_in_root_path")   # returns localized description
    set_locale("zh")                         # switch to Chinese
    _t("approval", "denied")                # returns Chinese string
"""

import json
import os
import threading
from pathlib import Path
from typing import Optional

# Thread-safe locale storage
_lock = threading.Lock()
_current_locale: str = "en"
_translations: dict[str, dict] = {}
_locales_loaded: bool = False


def _locales_dir() -> Path:
    """Return the path to the locales directory."""
    return Path(__file__).parent / "locales"


def _load_locales() -> None:
    """Load all locale files from the locales directory."""
    global _translations, _locales_loaded
    if _locales_loaded:
        return
    with _lock:
        if _locales_loaded:  # double-check after acquiring lock
            return
        locales_dir = _locales_dir()
        if not locales_dir.exists():
            _locales_loaded = True
            return
        for fp in locales_dir.glob("*.json"):
            try:
                with open(fp, encoding="utf-8") as f:
                    data = json.load(f)
                locale = data.get("_meta", {}).get("locale")
                if locale:
                    _translations[locale] = data
            except Exception:
                pass
        _locales_loaded = True


def _get_locale_from_env() -> str:
    """Detect the preferred locale from environment variables."""
    # HERMES_LOCALE env var takes precedence
    locale = os.getenv("HERMES_LOCALE")
    if locale:
        return locale
    # Also check common env vars used by other tools
    for env_key in ("LANG", "LC_ALL", "HERMES_LANG"):
        locale = os.getenv(env_key, "")
        if locale:
            # Extract language code (e.g. "en_US.UTF-8" -> "en")
            lang = locale.split("_")[0].split(".")[0].lower()
            if lang in _translations:
                return lang
    return "en"


def get_locale() -> str:
    """Return the currently active locale code (e.g. 'en', 'zh')."""
    return _current_locale


def set_locale(locale: str) -> None:
    """Set the current locale for this process.

    Args:
        locale: A locale code such as 'en' or 'zh'.
    """
    global _current_locale
    _load_locales()
    if locale not in _translations:
        raise ValueError(f"Unknown locale: {locale}. Available: {list(_translations.keys())}")
    with _lock:
        _current_locale = locale


def available_locales() -> list[str]:
    """Return a list of available locale codes."""
    _load_locales()
    return list(_translations.keys())


def _t(category: str, key: str, locale: Optional[str] = None, **kwargs) -> str:
    """Translate a string by category and key.

    Args:
        category: Top-level section in the locale JSON (e.g. "patterns", "approval").
        key:     Translation key within that section (e.g. "delete_in_root_path").
        locale:  Optional locale override (defaults to current locale).
        **kwargs: Format arguments for the translated string (e.g. description="foo").

    Returns:
        The translated string, falling back to the English string if the
        key/category is missing in the target locale, then to the key itself.
    """
    _load_locales()
    target = locale or _current_locale

    # Try target locale first, then English fallback, then raw key
    for try_locale in (target, "en"):
        data = _translations.get(try_locale, {})
        category_data = data.get(category, {})
        if key in category_data:
            template = category_data[key]
            if kwargs:
                return template.format(**kwargs)
            return template

    # Ultimate fallback: return the key itself
    if kwargs:
        return key.format(**kwargs)
    return key


def init_locale() -> None:
    """Initialize locale from environment. Called at import time by other modules."""
    _load_locales()
    global _current_locale
    detected = _get_locale_from_env()
    if detected in _translations:
        _current_locale = detected


# Auto-initialize when this module is imported
init_locale()
