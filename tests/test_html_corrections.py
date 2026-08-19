"""Tests for OCR HTML corrections."""

from rouen_ocr.html_work import MissingStepError
from rouen_ocr.html_corrections import HtmlCorrections


def test_group_nearby_text_divs_moves_closest_continuation_next() -> None:
    """Place a nearby text continuation before intervening page regions."""
    html = (
        '<section data-page-number="1">'
        '<div data-bbox="239 486 916 637" data-label="Text">first</div>'
        '<div data-bbox="87 645 252 706" data-label="Text">callout</div>'
        '<div data-bbox="243 649 548 941" data-label="Image">image</div>'
        '<div data-bbox="231 884 244 940" data-label="Caption">caption</div>'
        '<div data-bbox="563 635 916 904" data-label="Text">continuation</div>'
        '</section>'
    )

    corrected = HtmlCorrections(html).group_nearby_text_divs()
    section = corrected.soup.section
    assert section is not None

    regions = section.find_all("div", recursive=False)
    assert [region.get_text() for region in regions] == [
        "first",
        "continuation",
        "callout",
        "image",
        "caption",
    ]
    assert corrected.steps == ["group_nearby_text_divs"]


def test_group_nearby_text_divs_ignores_invalid_bboxes() -> None:
    """Leave malformed text regions in place without stopping correction."""
    html = (
        '<section data-page-number="1">'
        '<div data-bbox="invalid" data-label="Text">invalid</div>'
        '<div data-bbox="10 10 20 20" data-label="Text">valid</div>'
        '</section>'
    )

    corrected = HtmlCorrections(html).group_nearby_text_divs()

    assert str(corrected) == html


def test_correct_does_nothing_to_pure_text() -> None:
    """Test that pure text is returned as-is."""
    html = "hello, World!"
    corrected = HtmlCorrections(html).correct()

    assert str(corrected) == html


def test_correct_removes_chandra_divs() -> None:
    """Test that Chandra divs are removed."""
    html = '<div data-label="foo">hello</div> <div data-label="bar">world</div>'
    corrected = HtmlCorrections(html).remove_chandra_divs()

    assert str(corrected) == "hello world"
    assert corrected.steps == ["remove_chandra_divs"]


def test_correct_removes_unneeded_brs() -> None:
    """Test that unneeded br tags are removed."""
    html = "hello<br>world"
    corrected = (
        HtmlCorrections(html).
            remove_chandra_divs().
            remove_unneeded_brs()
    )

    assert str(corrected) == "hello world"


def test_correct_removes_unneeded_ps() -> None:
    """Test that unneeded p tags are merged."""
    html = (
        "<p>hello,</p><p>world</p>"
        "<p>hello, </p><p>world</p>"
        "<p>hello</p><p>world</p>"
    )
    corrected = (
        HtmlCorrections(html).
            remove_chandra_divs().
            remove_unneeded_ps()
    )

    assert str(corrected) == "<p>hello, world hello, world hello world</p>"


def test_remove_unneeded_ps_requires_lowercase_and_missing_period() -> None:
    """Keep paragraph boundaries when either merge condition is absent."""
    examples = [
        "<p>hello,</p><p>World</p>",
        "<p>hello.</p><p>world</p>",
    ]

    for html in examples:
        corrected = (
            HtmlCorrections(html).
                remove_chandra_divs().
                remove_unneeded_ps()
        )

        assert str(corrected) == html


def test_increase_heading_levels_in_page_sections() -> None:
    """Test that headings are pushed down one level in page sections."""
    html = (
        '<section data-page-number="1"><h1>Page 1</h1></section>'
        '<section data-page-number="2"><h2>Page 2</h2></section>'
        '<section data-page-number="3"><h6>Page 3</h6></section>'
        '<section data-page-number="4"><p><h3>Page 4</h3></p></section>'
    )
    corrected = (
        HtmlCorrections(html).
            remove_chandra_divs().
            increase_heading_levels()
    )

    assert str(corrected) == (
        '<section data-page-number="1"><h1>Page 1</h1></section>'
        '<section data-page-number="2"><h3>Page 2</h3></section>'
        '<section data-page-number="3"><h6>Page 3</h6></section>'
        '<section data-page-number="4"><p><h4>Page 4</h4></p></section>'
    )


def test_corrections_must_be_applied_in_order() -> None:
    """Test that corrections must be applied in the correct order."""
    html = "<p>hello,</p><p>world</p>"
    corrected = HtmlCorrections(html)

    try:
        corrected.remove_unneeded_ps()
    except MissingStepError as e:
        assert True
    else:
        assert False, "Expected MissingStepError was not raised."

    try:
        corrected.remove_unneeded_ps()
    except MissingStepError as e:
        assert True
    else:
        assert False, "Expected MissingStepError was not raised."
