"""A searchable PDF must embed a font for the selected OCR language."""
from unittest.mock import Mock

import pytest

from scripts import ocr_engine, pdf_utils


@pytest.mark.parametrize(
    "lang,script", [("hi", "Devanagari"), ("mr", "Devanagari"),
                    ("ta", "Tamil"), ("te", "Telugu")],
)
def test_linux_font_selection_uses_requested_script(monkeypatch, lang, script):
    """All Noto families installed: Tamil/Telugu must not pick Devanagari."""
    monkeypatch.delenv("INDIC_FONT_PATH", raising=False)
    monkeypatch.setattr(pdf_utils.os.path, "isfile", lambda p: "/noto/" in p)
    font = Mock()
    font.has_glyph.return_value = 1
    loader = Mock(return_value=font)
    monkeypatch.setattr(pdf_utils.fitz, "Font", loader)
    expected = f"/usr/share/fonts/truetype/noto/NotoSans{script}-Regular.ttf"
    assert pdf_utils._get_fontfile_for_lang(lang) == expected
    loader.assert_called_once_with(fontfile=expected)
    assert all(call.kwargs == {"fallback": False} for call in font.has_glyph.call_args_list)


@pytest.mark.parametrize("lang", ["hi", "mr", "ta", "te"])
def test_latin_only_linux_fonts_are_not_selected(monkeypatch, lang):
    monkeypatch.delenv("INDIC_FONT_PATH", raising=False)
    monkeypatch.setattr(pdf_utils.os.path, "isfile", lambda p: "dejavu" in p)
    assert pdf_utils._get_fontfile_for_lang(lang) is None


@pytest.mark.parametrize("broken", [False, True])
def test_custom_font_must_be_loadable_and_cover_script(monkeypatch, broken):
    monkeypatch.setenv("INDIC_FONT_PATH", "/custom.ttf")
    monkeypatch.setattr(pdf_utils.os.path, "isfile", lambda p: p == "/custom.ttf")
    font = Mock()
    font.has_glyph.return_value = 0
    monkeypatch.setattr(pdf_utils.fitz, "Font", Mock(
        side_effect=RuntimeError("Invalid font") if broken else None,
        return_value=font,
    ))
    assert pdf_utils._get_fontfile_for_lang("ta") is None


def test_unsupported_custom_font_falls_back_to_matching_system_font(monkeypatch):
    monkeypatch.setenv("INDIC_FONT_PATH", "/custom.ttf")
    monkeypatch.setattr(pdf_utils.os.path, "isfile", lambda p: True)
    def load_font(*, fontfile):
        font = Mock()
        font.has_glyph.return_value = int("NotoSansTelugu" in fontfile)
        return font
    monkeypatch.setattr(pdf_utils.fitz, "Font", load_font)
    assert pdf_utils._get_fontfile_for_lang("te").endswith("NotoSansTelugu-Regular.ttf")


def test_valid_custom_font_takes_precedence(monkeypatch):
    monkeypatch.setenv("INDIC_FONT_PATH", "/custom.ttf")
    monkeypatch.setattr(pdf_utils.os.path, "isfile", lambda p: True)
    font = Mock()
    font.has_glyph.return_value = 1
    monkeypatch.setattr(pdf_utils.fitz, "Font", Mock(return_value=font))
    assert pdf_utils._get_fontfile_for_lang("mr") == "/custom.ttf"


def test_missing_font_fails_before_decrypting_or_creating_output(monkeypatch, tmp_path):
    engine = Mock()
    monkeypatch.setattr(ocr_engine, "get_ocr_engine", lambda: engine)
    monkeypatch.setattr(pdf_utils, "_get_fontfile_for_lang", lambda lang: None)
    decrypt = Mock()
    monkeypatch.setattr(pdf_utils, "_get_decrypted_pdf_path", decrypt)
    with pytest.raises(ValueError, match="missing a required font"):
        pdf_utils.ocr_pdf_to_searchable_pdf("scan.pdf", str(tmp_path), lang="ta")
    decrypt.assert_not_called()
    engine.recognize.assert_not_called()
    assert list(tmp_path.iterdir()) == []
