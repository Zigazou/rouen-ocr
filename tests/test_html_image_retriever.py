"""Tests for HTML image discovery and PDF extraction."""

import sys
from types import SimpleNamespace

from rouen_ocr.html_image_retriever import HtmlImageRetriever


class FakeRect:
    """Minimal rectangle implementation used to isolate the PyMuPDF boundary."""

    def __init__(self, *values: object) -> None:
        if len(values) == 1:
            values = tuple(values[0])
        self.x0, self.y0, self.x1, self.y1 = values

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    def __and__(self, other: "FakeRect") -> "FakeRect":
        return FakeRect(
            max(self.x0, other.x0),
            max(self.y0, other.y0),
            min(self.x1, other.x1),
            min(self.y1, other.y1),
        )

    @property
    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0

    def get_area(self) -> float:
        return max(0, self.width) * max(0, self.height)


def test_find_images_ignores_invalid_bounding_boxes(capsys) -> None:
    retriever = HtmlImageRetriever(
        '<div data-bbox="10 20 30 40" data-label="Image"></div>'
        '<div data-bbox="invalid" data-label="Image"></div>'
    )

    assert [bbox.id("image") for bbox in retriever.find_images()] == [
        "image-10-20-30-40"
    ]
    assert "Invalid data-bbox" in capsys.readouterr().out


def test_extract_images_prefers_an_exact_native_pdf_image(
    monkeypatch, tmp_path
) -> None:
    class FakePage:
        rect = FakeRect(0, 0, 200, 100)

        @staticmethod
        def get_image_info(*, xrefs: bool) -> list[dict]:
            assert xrefs is True
            return [{"bbox": (0, 0, 100, 50), "xref": 7}]

    class FakeDocument:
        def __enter__(self) -> "FakeDocument":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        @staticmethod
        def extract_image(xref: int) -> dict:
            assert xref == 7
            return {"image": b"native image", "ext": "jpeg", "smask": 0}

        @staticmethod
        def __getitem__(page_number: int) -> FakePage:
            assert page_number == 0
            return FakePage()

    fake_pymupdf = SimpleNamespace(Rect=FakeRect, open=lambda _: FakeDocument())
    monkeypatch.setitem(sys.modules, "pymupdf", fake_pymupdf)

    retriever = HtmlImageRetriever(
        '<div data-bbox="0 0 500 500" data-label="Image"></div>'
    )

    paths = retriever.extract_images("source.pdf", 0, tmp_path)

    assert paths == [tmp_path / "page-0001-image-0001-0-0-500-500.jpeg"]
    assert paths[0].read_bytes() == b"native image"
