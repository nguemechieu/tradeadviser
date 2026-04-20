import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from frontend.ui.i18n import normalize_language_code, translate, translate_rich_text, translate_text


def test_normalize_language_code_falls_back_to_base_language():
    assert normalize_language_code("fr-FR") == "fr"
    assert normalize_language_code("es-419") == "es"


def test_translate_uses_requested_language_and_english_fallback():
    assert translate("fr", "terminal.menu.file") == "Fichier"
    assert translate("de", "terminal.menu.file") == "File"
    assert translate("en", "missing.key") == "missing.key"


def test_translate_text_handles_multiline_dynamic_sections():
    text = "Current Assignment\nSymbol: EUR/USD\nLocked: No"
    translated = translate_text("fr", text)

    assert translated.splitlines()[0] == "Affectation actuelle"
    assert "Symbole: EUR/USD" in translated
    assert "Verrouille: Non" in translated


def test_translate_text_handles_segmented_status_lines():
    text = "Approved: 2  |  Rejected: 1  |  Execution: 3"
    translated = translate_text("es", text)

    assert translated == "Aprobado: 2  |  Rechazado: 1  |  Ejecucion: 3"


def test_translate_text_handles_trailing_count_suffixes():
    assert translate_text("pt", "Notification Center (3)") == "Central de notificacoes (3)"


def test_translate_rich_text_preserves_html_and_translates_visible_content():
    text = "<h3>System Health</h3><p>Notification Center (3)</p>"
    translated = translate_rich_text("fr", text)

    assert translated == "<h3>Sante systeme</h3><p>Centre de notifications (3)</p>"
