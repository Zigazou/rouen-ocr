"""Tests for the PDF-to-text command."""

from pathlib import Path

import pytest

from rouen_ocr.pdf_to_text import (
    OCR_PROMPT,
    convert_pdf_to_text,
    default_images_dir,
    html_fragment,
    ocr_image,
)


def test_default_images_dir_uses_output_stem() -> None:
    """Rendered pages are placed beside the requested text output by default."""
    assert default_images_dir(Path("results/document.txt")) == Path(
        "results/document-pages"
    )


def test_ocr_prompt_includes_rouen_vocabulary() -> None:
    """Ambiguous OCR terms can be matched against the project vocabulary."""
    assert "Rouen vocabulary" in OCR_PROMPT
    assert "Métropole Rouen Normandie" in OCR_PROMPT


def test_ocr_image_uses_structured_html_response(monkeypatch, tmp_path: Path) -> None:
    """The structured response is extracted from the schema's HTML property."""
    image_path = tmp_path / "page.png"

    def fake_chat(**kwargs: object) -> object:
        assert kwargs == {
            "model": "chandra-ocr-2",
            "messages": [
                {
                    "role": "user",
                    "content": OCR_PROMPT,
                    "images": [image_path],
                }
            ],
            "options": {"temperature": 0},
            "think": False,
        }
        return type(
            "Response",
            (),
            {
                "message": type(
                    "Message", (), {"content": '{"html": "<p>Document text</p>"}'}
                )()
            },
        )()

    monkeypatch.setattr("rouen_ocr.pdf_to_text.ollama.chat", fake_chat)

    assert ocr_image(image_path, "chandra-ocr-2") == "<p>Document text</p>"


def test_ocr_image_rejects_missing_structured_html(monkeypatch, tmp_path: Path) -> None:
    """An incomplete structured response cannot be written as an OCR result."""
    def fake_chat(**kwargs: object) -> object:
        return type(
            "Response",
            (),
            {"message": type("Message", (), {"content": "{}"})()},
        )()

    monkeypatch.setattr("rouen_ocr.pdf_to_text.ollama.chat", fake_chat)

    with pytest.raises(ValueError, match="did not return structured HTML"):
        ocr_image(tmp_path / "page.png", "chandra-ocr-2")


def test_convert_pdf_to_text_renders_ocr_and_writes_result(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """Each rendered page is sent to the loaded model and the output is HTML."""
    images_dir = tmp_path / "pages"
    output_text = tmp_path / "output" / "document.txt"

    def fake_convert(*args: object) -> int:
        progress_callback = args[3]
        assert callable(progress_callback)
        for completed in range(3):
            progress_callback(completed, 2)
        return 2

    monkeypatch.setattr("rouen_ocr.pdf_to_text.convert_pdf", fake_convert)
    calls: list[Path] = []

    def fake_ocr(image: Path, received_model_name: str) -> str:
        calls.append(image)
        assert received_model_name == "chandra-ocr-2"
        return f"<p>text {len(calls)}</p>"

    monkeypatch.setattr("rouen_ocr.pdf_to_text.ocr_image", fake_ocr)

    assert convert_pdf_to_text(
        tmp_path / "input.pdf", output_text, images_dir, model_name="chandra-ocr-2"
    ) == 2
    assert calls == [images_dir / "page-0001.png", images_dir / "page-0002.png"]
    assert output_text.read_text(encoding="utf-8") == (
        "<!doctype html>\n"
        "<html>\n"
        '<head><meta charset="utf-8"></head>\n'
        "<body>\n"
        '<section data-page-number="1">\n'
        "<p>text 1</p>\n"
        "</section>\n"
        '<section data-page-number="2">\n'
        "<p>text 2</p>\n"
        "</section>\n"
        "</body>\n"
        "</html>\n"
    )
    assert capsys.readouterr().out == (
        "Rendering: 0/2 page(s)\n"
        "Rendering: 1/2 page(s)\n"
        "Rendering: 2/2 page(s)\n"
        "OCRizing: 0/2 page(s)\n"
        "OCRizing: 1/2 page(s)\n"
        "OCRizing: 2/2 page(s)\n"
    )


def test_html_fragment_discards_reasoning_and_document_wrapper() -> None:
    """Reasoning and non-HTML wrapper text are never written to the output."""
    response = """<think>Need to transcribe the page first.</think>
    Here is the result:
    ```html
    <html><body><p>Document text</p></body></html>
    ```"""

    assert html_fragment(response) == "<p>Document text</p>"


def test_html_fragment_discards_non_html_text_outside_the_markup() -> None:
    """Only the HTML portion of a response is retained."""
    assert html_fragment("Result: <p>Document text</p> Done.") == "<p>Document text</p>"


def test_html_fragment_rejects_non_html_model_output() -> None:
    """A response without HTML cannot accidentally be saved as OCR content."""
    with pytest.raises(ValueError, match="did not return HTML"):
        html_fragment("<think>OCR page</think>Document text")
