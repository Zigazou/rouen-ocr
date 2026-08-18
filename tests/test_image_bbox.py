"""Tests for Image BBox class."""

from rouen_ocr.image_bbox import ImageBBox


def test_from_chandra_attribute_valid() -> None:
    """Test that ImageBBox can be created from a Chandra attribute string."""
    attribute = "10 20 30 40"
    bbox = ImageBBox.from_chandra_attribute(attribute)

    assert bbox.x0_1000 == 10
    assert bbox.y0_1000 == 20
    assert bbox.x1_1000 == 30
    assert bbox.y1_1000 == 40


def test_from_chandra_attribute_invalid() -> None:
    """Test that ImageBBox raises ValueError for invalid Chandra attribute
    strings.
    """
    invalid_attributes = [
        "1 2 3 1111",      # Too large value
        "10 20 30",        # Too few values
        "10 20 30 40 50",  # Too many values
        "10 20 thirty 40",  # Non-integer value
        "10,20,30,40",     # Comma-separated values
        "",                # Empty string
    ]

    for attribute in invalid_attributes:
        try:
            ImageBBox.from_chandra_attribute(attribute)
        except ValueError as e:
            assert str(e).startswith("Invalid")
        else:
            assert False, f"Expected ValueError for attribute: {attribute}"


def test_translate_coordinates() -> None:
    """Test that ImageBBox translates coordinates correctly."""

    image_width = 1000
    image_height = 2000

    bboxes = [
        ImageBBox(100, 200, 300, 400),
        ImageBBox(0, 0, 0, 0),
        ImageBBox(0, 0, 1000, 1000),
    ]

    expecteds = [
        (100, 400, 300, 800),
        (0, 0, 0, 0),
        (0, 0, image_width, image_height),
    ]

    tests = zip(bboxes, expecteds)

    for bbox, expected in tests:
        translated = bbox.translate_coordinates(image_width, image_height)
        assert translated == expected

def test_id_generation() -> None:
    """Test that ImageBBox generates unique identifiers correctly."""
    bbox = ImageBBox(10, 20, 30, 40)
    base = "page1"
    expected_id = "page1-10-20-30-40"

    assert bbox.id(base) == expected_id