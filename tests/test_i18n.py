"""Translation completeness and explicit separation from user content."""

import ast
from pathlib import Path
from string import Formatter

import pytest
from PySide6.QtWidgets import QDialogButtonBox

from datadesk.i18n import catalog, join_tr, language, render_text, set_language, tr


def test_translated_notices_can_be_rendered_again_without_translating_values(qapp):
    previous = language()
    try:
        from datadesk import translations_workspace  # noqa: F401

        set_language("tr")
        original = tr("Yeni dosya")
        notice = join_tr("\n", [original, "Yeni dosya"])
        set_language("en")
        assert render_text(notice) == "New file\nYeni dosya"
        assert str(original) == "Yeni dosya"
        assert tr("{value}", value="Yeni dosya") == "Yeni dosya"
    finally:
        set_language(previous)


def test_all_explicit_translation_keys_have_matching_placeholders():
    from datadesk import ui, settings_ui  # noqa: F401

    translations = catalog()
    missing = []
    for path in (Path(__file__).parents[1] / "datadesk").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                key = node.args[0].value
                if key not in translations:
                    missing.append((path.name, node.lineno, key))
    assert not missing
    formatter = Formatter()
    for source, target in translations.items():
        source_fields = {
            (name, spec, conversion)
            for _, name, spec, conversion in formatter.parse(source)
            if name is not None
        }
        target_fields = {
            (name, spec, conversion)
            for _, name, spec, conversion in formatter.parse(target)
            if name is not None
        }
        assert source_fields == target_fields, source


@pytest.mark.parametrize("code, expected", [("tr", "İptal"), ("en", "Cancel")])
def test_standard_qt_dialog_controls_follow_selected_language(qapp, code, expected):
    previous = language()
    try:
        set_language(code)
        assert qapp._datadesk_translation_loaded
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        assert box.buttons()[0].text() == expected
    finally:
        set_language(previous)
