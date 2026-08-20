"""Tests for the PDF-to-text command."""

from pathlib import Path

import pytest

from rouen_ocr.pdf_to_text import (
    convert_pdf_to_text,
    default_images_dir,
    html_document,
    ocr_image,
    ocr_prompt,
)


def test_default_images_dir_uses_output_stem() -> None:
    """Rendered pages are placed beside the requested text output by default."""
    assert default_images_dir(Path("results/document.txt")) == Path(
        "results/document-pages"
    )


def test_ocr_image_returns_the_model_response(monkeypatch, tmp_path: Path) -> None:
    """The raw HTML response is returned from the model message."""
    image_path = tmp_path / "page.png"

    def fake_chat(**kwargs: object) -> object:
        assert kwargs == {
            "model": "hf.co/prithivMLmods/Chandra-OCR-2-GGUF:Q4_K_M",
            "messages": [
                {
                    "role": "user",
                    "content": ocr_prompt("magazine", 2),
                    "images": [image_path],
                }
            ],
            "options": {
                "temperature": 0.0,
                "top_p": 0.1,
                "num_ctx": 16384,
                "num_predict": 12384,
                "repeat_penalty": 1.0,
                "seed": 0,
            },
            "think": False,
        }
        return type(
            "Response",
            (),
            {
                "message": type(
                    "Message", (), {"content": "<p>Document text</p>"}
                )()
            },
        )()

    monkeypatch.setattr("rouen_ocr.pdf_to_text.chat", fake_chat)

    assert ocr_image(image_path, "magazine", 2) == "<p>Document text</p>"


def test_ocr_image_rejects_missing_response_content(
    monkeypatch, tmp_path: Path
) -> None:
    """An empty model response cannot be written as an OCR result."""

    def fake_chat(**kwargs: object) -> object:
        return type(
            "Response",
            (),
            {"message": type("Message", (), {"content": ""})()},
        )()

    monkeypatch.setattr("rouen_ocr.pdf_to_text.chat", fake_chat)

    with pytest.raises(ValueError, match="did not contain any content"):
        ocr_image(tmp_path / "page.png", "chandra-ocr-2")


def test_convert_pdf_to_text_renders_ocr_and_writes_result(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """Each rendered page is sent to OCR and written into the HTML output."""
    images_dir = tmp_path / "pages"
    output_text = tmp_path / "output" / "document.txt"

    def fake_convert(*args: object) -> int:
        progress_callback = args[3]
        assert callable(progress_callback)
        for completed in range(1, 3):
            progress_callback(completed, 2)
        return 2

    monkeypatch.setattr("rouen_ocr.pdf_to_text.convert_pdf", fake_convert)
    calls: list[Path] = []

    def fake_ocr(
        image: Path, received_document_type: str, page_number: int
    ) -> str:
        calls.append(image)
        assert received_document_type == "auto"
        assert page_number == len(calls)
        return f"<p>text {len(calls)}</p>"

    monkeypatch.setattr("rouen_ocr.pdf_to_text.ocr_image", fake_ocr)
    monkeypatch.setattr(
        "rouen_ocr.pdf_to_text.HtmlImageRetriever.replace_images",
        lambda self, *_args: self,
    )

    assert convert_pdf_to_text(
        tmp_path / "input.pdf", output_text, images_dir, document_type="auto"
    ) == 2
    assert calls == [images_dir / "page-0001.png", images_dir / "page-0002.png"]

    output = output_text.read_text(encoding="utf-8")
    assert '<section data-page-number="1">' in output
    assert '<section data-page-number="2">' in output
    assert "<p>text 1</p>" in output
    assert "<p>text 2</p>" in output
    assert capsys.readouterr().out == (
        "Rendering: page 1 of 2\n"
        "Rendering: page 2 of 2\n"
    )


def test_html_document_wraps_page_fragments() -> None:
    """OCR fragments are wrapped in numbered page sections."""
    output = str(html_document(["<p>Page one</p>", "<p>Page two</p>"]))

    assert output.startswith("<!DOCTYPE html>")
    assert '<section data-page-number="1"><p>Page one</p></section>' in output
    assert '<section data-page-number="2"><p>Page two</p></section>' in output
