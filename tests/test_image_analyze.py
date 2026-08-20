"""Tests for the image_analyze module."""

from pathlib import Path

from rouen_ocr.image_analyze import analyze_image


def test_photo() -> None:
    """Test that a photo is correctly analyzed as 'photo'."""

    # Load balcon.jpg from the tests directory.
    image_path = Path(__file__).parent / "balcon.jpg"
    with open(image_path, "rb") as f:
        image_data = f.read()

    analysis = analyze_image(image_data)

    assert analysis == "photo"

def test_big_letter() -> None:
    """Test that a big letter is correctly analyzed as 'big letter'."""

    # Load lettrine.jpg from the tests directory.
    image_path = Path(__file__).parent / "lettrine.jpg"
    with open(image_path, "rb") as f:
        image_data = f.read()

    analysis = analyze_image(image_data)

    assert analysis == "big letter"
