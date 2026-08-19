"""Tests for the PDF-to-text command."""

from pathlib import Path

from rouen_ocr.textual_alternative import alt_image


def test_sample_image() -> None:
    """Rendered pages are placed beside the requested text output by default."""

    # Load balcon.jpg from the tests directory.
    image_path = Path(__file__).parent / "balcon.jpg"
    with open(image_path, "rb") as f:
        image_data = f.read()

    alt_text = alt_image(image_data)

    assert alt_text == "Balconnet en façade d'un bâtiment avec garde-corps en métal décoré de motifs floraux et géométriques, fixé sur une structure en pierre pâle."
