"""Tests for Image BBox class."""

import pytest

from rouen_ocr.bbox import BBox


def test_from_chandra_attribute_valid() -> None:
    """Test that BBox can be created from a Chandra attribute string."""
    attribute = "10 20 30 40"
    bbox = BBox.from_chandra_attribute(attribute)

    assert bbox.x0_1000 == 10
    assert bbox.y0_1000 == 20
    assert bbox.x1_1000 == 30
    assert bbox.y1_1000 == 40


def test_from_chandra_attribute_invalid() -> None:
    """Test that BBox raises ValueError for invalid Chandra attribute
    strings.
    """
    invalid_attributes = [
        "1 2 3 1111",      # Too large value
        "10 20 30",        # Too few values
        "10 20 30 40 50",  # Too many values
        "10 20 thirty 40", # Non-integer value
        "10,20,30,40",     # Comma-separated values
        "",                # Empty string
    ]

    for attribute in invalid_attributes:
        try:
            BBox.from_chandra_attribute(attribute)
        except ValueError as e:
            assert str(e).startswith("Invalid")
        else:
            assert False, f"Expected ValueError for attribute: {attribute}"


def test_translate_coordinates() -> None:
    """Test that BBox translates coordinates correctly."""

    image_width = 1000
    image_height = 2000

    bboxes = [
        BBox(100, 200, 300, 400),
        BBox(0, 0, 0, 0),
        BBox(0, 0, 1000, 1000),
    ]

    expecteds = [
        (100, 400, 300, 800),
        (0, 0, 0, 0),
        (0, 0, image_width, image_height),
    ]

    for bbox, expected in zip(bboxes, expecteds):
        translated = bbox.translate_coordinates(image_width, image_height)
        assert translated == expected


def test_overlaps_with() -> None:
    """Test overlapping and non-overlapping bounding boxes."""
    bbox = BBox(100, 100, 300, 300)

    assert bbox.overlaps_with(BBox(200, 200, 400, 400))
    assert bbox.overlaps_with(BBox(300, 300, 500, 500))
    assert not bbox.overlaps_with(BBox(301, 301, 500, 500))
    assert not bbox.overlaps_with(BBox(400, 100, 500, 200))


def test_is_before() -> None:
    """Test top-to-bottom, then left-to-right bounding-box ordering."""
    bbox = BBox(100, 100, 300, 300)

    assert bbox.is_before(BBox(100, 200, 300, 400))
    assert bbox.is_before(BBox(200, 100, 400, 300))
    assert not bbox.is_before(BBox(50, 100, 250, 300))
    assert not bbox.is_before(BBox(50, 50, 250, 250))


def test_smallest_distance_to_border() -> None:
    """Test zero, edge, and diagonal distances between bounding boxes."""
    bbox = BBox(100, 100, 300, 300)

    assert bbox.smallest_distance_to_border(BBox(200, 200, 400, 400)) == 0.0
    assert bbox.smallest_distance_to_border(BBox(300, 100, 500, 300)) == 0.0
    assert bbox.smallest_distance_to_border(BBox(400, 100, 500, 300)) == 100.0
    assert bbox.smallest_distance_to_border(BBox(400, 500, 500, 600)) == pytest.approx(
        (100**2 + 200**2) ** 0.5
    )

def test_id_generation() -> None:
    """Test that BBox generates unique identifiers correctly."""
    base = "page1"

    assert BBox(1, 2, 3, 4).id(base) == "page1-1-2-3-4"
    assert BBox(1, 2, 3, 4, 3).id(base) == "page1-1-2-3-4"
    assert BBox(1, 2, 3, 4, 3).id() == "page3-1-2-3-4"
    assert BBox(1, 2, 3, 4).id() == "bbox-1-2-3-4"