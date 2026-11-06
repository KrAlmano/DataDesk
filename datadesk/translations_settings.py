"""English settings labels; language names remain recognizable in either locale."""

from .i18n import register_translations

TRANSLATIONS = {
    "DataDesk · Ayarlar": "DataDesk · Settings",
    "Görünüm ve dil": "Appearance and language",
    "Arayüz dili": "Interface language",
    "Tema": "Theme",
    "Arayüz boyutu": "Interface size",
    "Açık": "Light",
    "Koyu": "Dark",
    "Sistem": "System",
    "Dil seçimi yalnızca arayüzü değiştirir. Dosyalarınız ve hücre içerikleri değişmez.": (
        "The language setting changes the interface only. Your files and cell contents stay the same."
    ),
    "Uygula": "Apply",
    "Vazgeç": "Cancel",
}

register_translations(TRANSLATIONS)
