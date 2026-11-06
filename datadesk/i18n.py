"""Explicit UI translations; user data is never used as a translation key."""

from pathlib import Path

_LANGUAGE = "tr"
_TRANSLATIONS = {}


def register_translations(mapping):
    for source, translated in mapping.items():
        previous = _TRANSLATIONS.get(source)
        if previous is not None and previous != translated:
            raise ValueError(f"Conflicting translation for {source!r}: {previous!r} / {translated!r}")
        _TRANSLATIONS[source] = translated


def language():
    return _LANGUAGE


def catalog():
    return dict(_TRANSLATIONS)


class LocalizedText(str):
    """A normal string that can also be rendered again after a language change."""

    def __new__(cls, source, values):
        instance = super().__new__(cls, _render(source, values))
        instance.source = source
        instance.values = values
        return instance

    def render(self):
        return _render(self.source, self.values)


class JoinedText(str):
    def __new__(cls, separator, parts):
        parts = tuple(parts)
        instance = super().__new__(cls, separator.join(render_text(part) for part in parts))
        instance.separator = separator
        instance.parts = parts
        return instance

    def render(self):
        return self.separator.join(render_text(part) for part in self.parts)


def render_text(value):
    return value.render() if isinstance(value, (LocalizedText, JoinedText)) else str(value)


def _render(source, values):
    template = _TRANSLATIONS.get(source, source) if _LANGUAGE == "en" else source
    if not values:
        return template
    rendered = {
        key: render_text(value) if isinstance(value, (LocalizedText, JoinedText)) else value
        for key, value in values.items()
    }
    return template.format(**rendered)


def tr(source, **values):
    return LocalizedText(source, values)


def join_tr(separator, values):
    return JoinedText(separator, values)


def set_language(code):
    global _LANGUAGE
    if code not in {"tr", "en"}:
        raise ValueError(f"Unsupported language: {code}")
    _LANGUAGE = code
    _configure_qt(code)


def _configure_qt(code):
    # Import lazily: data processing can run without a desktop application.
    from PySide6.QtCore import QCoreApplication, QLibraryInfo, QLocale, QTranslator

    QLocale.setDefault(QLocale("tr_TR" if code == "tr" else "en_GB"))
    app = QCoreApplication.instance()
    if app is None:
        return
    previous = getattr(app, "_datadesk_translator", None)
    if previous is not None:
        app.removeTranslator(previous)
    translator = QTranslator(app)
    filename = f"qtbase_{code}.qm"
    candidates = (
        Path(__file__).parent / "assets" / "qt" / filename,
        Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)) / filename,
    )
    loaded = any(translator.load(str(path)) for path in candidates if path.is_file())
    if loaded:
        app.installTranslator(translator)
    app._datadesk_translator = translator
    app._datadesk_translation_loaded = loaded
    if previous is not None:
        previous.deleteLater()
