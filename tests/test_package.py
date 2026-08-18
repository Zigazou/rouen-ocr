"""Basic package checks."""

import rouen_ocr


def test_package_is_importable() -> None:
    """The package can be imported."""
    assert rouen_ocr is not None
