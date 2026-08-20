"""Tests for the PDF image conversion command."""

import argparse

import pytest

from rouen_ocr.pdf_to_images import positive_scale


def test_positive_scale_accepts_positive_numbers() -> None:
    """A positive integer scale can be supplied on the command line."""
    assert positive_scale("2") == 2


@pytest.mark.parametrize("value", ["0", "-1", "2.5", "not-a-number"])
def test_positive_scale_rejects_invalid_values(value: str) -> None:
    """Zero, negative, fractional, and non-numeric scales are rejected."""
    with pytest.raises(argparse.ArgumentTypeError):
        positive_scale(value)
