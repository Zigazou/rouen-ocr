"""Tests for HTML image discovery and PDF extraction."""

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


def test_find_images_reads_images_from_page_sections() -> None:
    retriever = HtmlImageRetriever(
        '<section data-page-number="2">'
        '<div data-bbox="10 20 30 40" data-label="Image"></div>'
        '</section>'
        '<div data-bbox="50 60 70 80" data-label="Image"></div>'
    )

    assert [bbox.id() for bbox in retriever.bboxes] == [
        "page2-10-20-30-40"
    ]


def test_extract_images_prefers_an_exact_native_pdf_image(monkeypatch) -> None:
    class FakePage:
        rect = FakeRect(0, 0, 200, 100)

        @staticmethod
        def get_image_info(*, xrefs: bool) -> list[dict]:
            assert xrefs is True
            return [{"bbox": (0, 0, 100, 50), "xref": 7}]

    class FakeDocument:
        def __len__(self) -> int:
            return 1

        @staticmethod
        def __getitem__(page_number: int) -> FakePage:
            assert page_number == 0
            return FakePage()

    retriever = HtmlImageRetriever(
        '<section data-page-number="1">'
        '<div data-bbox="0 0 500 500" data-label="Image"></div>'
        '</section>'
    )
    retriever.document = FakeDocument()
    monkeypatch.setattr(retriever, "_image_bytes", lambda xref: b"native image")

    retriever.extract_images(1)

    assert retriever.images["page1-0-0-500-500"] == b"native image"
