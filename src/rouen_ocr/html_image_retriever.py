"""Find and extract the images described by Chandra HTML.

This class only works with HTML that has been returned by the Chandra OCR 2
model, which uses div tags with a data-label attribute set to "Image" to
identify images. The HTML must not have been modified by any other process, such
as the HTML corrections applied by the HtmlCorrections class.

The data-bbox attribute of the div tag contains the bounding box of the image.
The coordinates are normalized to a 0--1000 page coordinate system.
"""

from __future__ import annotations
from base64 import b64encode
from typing import Callable, Self

from pymupdf import Document, Pixmap, Matrix, Rect

from PIL import Image
from io import BytesIO
from pathlib import Path

from rouen_ocr.html_work import HtmlWork
from rouen_ocr.image_bbox import ImageBBox

PYMUPDF_JPEG = "jpg"
PIL_JPEG = "JPEG"


class HtmlImageRetriever(HtmlWork):
    def __init__(self, html: str) -> None:
        """Initialize the retriever with the HTML document or fragment.

        Input:
            html: The HTML document or fragment to process.
        """
        super().__init__(html)

        self.document = None
        self.images = {}

    def find_images(self) -> list[ImageBBox]:
        """Find all images in the HTML document or fragment.

        Images are identified by a div tag with an attribute data-label set to
        "Image", i.e. `<div data-bbox="78 12 146 83" data-label="Image">`.

        Output:
            A list of all ImageBBox instances in the HTML.

        """

        # Find all section tags with a data-page-number attribute.
        sections = self.soup.find_all(
            "section",
            attrs={"data-page-number": True}
        )

        bboxes = []
        for section in sections:
            page_number = section.get("data-page-number")
            if not isinstance(page_number, str) or not page_number.isdigit():
                continue

            page_number = int(page_number)

            # Find images in the current page.
            divs = section.find_all("div", {"data-label": "Image"})
            for div in divs:
                bbox_str = div.get("data-bbox")

                if not isinstance(bbox_str, str):
                    continue

                bboxes.append(
                    ImageBBox.from_chandra_attribute(bbox_str, page_number)
                )

        return bboxes

    def replace_images(
        self,
        pdf_path: str | Path,
        show_progress_replacing: Callable[[int, int], None]
    ) -> Self:
        """Replace all images in the HTML document with data URI.

        Input:
            pdf_path: The path to the PDF file containing the original images.
            show_progress_replacing: A callback function to show progress of
                image replacement. It takes two arguments: the number of images
                replaced so far and the total number of images to replace.
        """
        self.document = Document(pdf_path)

        # Extract images page by page.
        for page_number in range(len(self.document)):
            show_progress_replacing(page_number + 1, len(self.document))
            self.extract_images(page_number + 1)

        # Replace the div tags with the extracted images.
        for bbox in self.find_images():
            div = self.soup.find(
                "div",
                {"data-bbox": bbox.to_chandra_attribute()}
            )

            if div is None:
                continue

            # Find the corresponding image bytes for this bounding box.
            image_bytes = self.images.get(bbox.id(), None)
            if image_bytes is None:
                continue

            # Replace the div tag with an img tag containing the data URI of the
            # extracted image.
            data_uri = (
                "data:image/jpeg;base64,"
                f"{b64encode(image_bytes).decode('utf-8')}"
            )

            div.clear()
            div.append(self.soup.new_tag("img", src=data_uri))

        return self

    def extract_images(
        self,
        page_number: int,
        render_scale: int = 2,
        match_threshold: float = 0.90,
    ) -> None:
        """Extract the images found in this HTML fragment from a PDF page.

        A matching PDF image object is written in its original format whenever
        its displayed bounding box closely matches Chandra's bounding box. If
        the Chandra box is contained in a larger PDF image, the original image
        is cropped instead. Vector artwork and unmatched regions fall back to a
        clipped rendering of the page.

        Input:
            page_number: One-based number of the PDF page matching this HTML.
            render_scale: Resolution multiplier for rendered fallbacks.
            match_threshold: Minimum target coverage required to use a native
                PDF image instead of rendering the page.

        Output:
            None. Extracted images are stored in ``self.images``.

        Raises:
            ValueError: If ``page_number`` or an extraction option is invalid.
        """
        assert self.document is not None, "PDF document is not open."
        assert page_number > 0, "page_number must be strictly positive."
        assert render_scale > 0, "render_scale must be strictly positive."
        assert 0 < match_threshold <= 1, (
            "match_threshold must be in the range (0, 1]."
        )

        try:
            page = self.document[page_number - 1]
        except IndexError as error:
            raise ValueError(
                f"PDF does not contain page {page_number}."
            ) from error

        image_infos = page.get_image_info(xrefs=True)

        for bbox in self.find_images():
            target = self._pdf_rect(page.rect, bbox)
            bbox_id = bbox.id()
            candidate = self._best_image_candidate(image_infos, target)

            if candidate is not None:
                info, image_rect, coverage = candidate
                xref = info.get("xref", 0)
                if xref > 0 and coverage >= match_threshold:
                    image_area = image_rect.get_area()
                    target_area = target.get_area()
                    if image_area <= target_area / match_threshold:
                        self.images[bbox_id] = self._image_bytes(xref)

                        continue

                    if (
                        self._contains(image_rect, target) and
                        self._is_axis_aligned(info)
                    ):
                        self.images[bbox_id] = self._get_native_crop(
                            xref,
                            image_rect,
                            target
                        )

                        continue

            pixmap = page.get_pixmap(
                matrix=Matrix(render_scale, render_scale),
                clip=target,
                alpha=False,
                annots=False,
            )

            self.images[bbox_id] = pixmap.tobytes("JPEG")

    def _pdf_rect(self, page_rect: Rect, bbox: ImageBBox) -> Rect:
        """Translate a normalized Chandra bounding box to PDF coordinates.

        Input:
            page_rect: The bounding box of the PDF page in PDF coordinates.
            bbox: The Chandra bounding box in normalized coordinates.

        Output:
            A Rect object representing the bounding box in PDF coordinates.
        """
        return Rect(
            page_rect.x0 + bbox.x0_1000 / 1000 * page_rect.width,
            page_rect.y0 + bbox.y0_1000 / 1000 * page_rect.height,
            page_rect.x0 + bbox.x1_1000 / 1000 * page_rect.width,
            page_rect.y0 + bbox.y1_1000 / 1000 * page_rect.height,
        )

    def _best_image_candidate(
        self,
        image_infos: list[dict],
        target: Rect
    ) -> tuple[dict, Rect, float] | None:
        """Return the PDF image that covers the largest part of ``target``.

        Input:
            image_infos: List of dictionaries returned by PyMuPDF's
                `get_image_info()`.
            target: The bounding box of the Chandra region in page coordinates.

        Output:
            A tuple of (image_info, image_rect, coverage) for the best
            candidate, or None if no candidate covers any part of the target.
        """
        best = None
        for info in image_infos:
            image_rect = Rect(info["bbox"])
            intersection = image_rect & target
            if intersection.is_empty or target.get_area() == 0:
                continue

            coverage = intersection.get_area() / target.get_area()
            if best is None or coverage > best[2]:
                best = (info, image_rect, coverage)

        return best

    def _contains(self, outer: Rect, inner: Rect) -> bool:
        """Return whether ``outer`` completely contains ``inner``."""
        return (
            outer.x0 <= inner.x0 and
            outer.y0 <= inner.y0 and
            outer.x1 >= inner.x1 and
            outer.y1 >= inner.y1
        )

    def _is_axis_aligned(self, info: dict) -> bool:
        """Return whether a PDF image can be cropped without rotation handling.

        Input:
            info: The dictionary returned by PyMuPDF's get_image_info().
        """
        transform = info.get("transform")

        if transform is None:
            return True

        return (transform[1] == 0 and transform[2] == 0)

    def _image_bytes(self, xref: int) -> bytes:
        """Return image data, reconstructing a soft mask when one is present."""
        if self.document is None:
            raise RuntimeError("PDF document is not open.")

        image = self.document.extract_image(xref)
        soft_mask_xref = image.get("smask", 0)
        pixmap = Pixmap(self.document, xref)

        if soft_mask_xref <= 0:
            # No soft mask, so we can return the image bytes directly.
            return pixmap.tobytes(PYMUPDF_JPEG)

        # Retrieve the soft mask and combine it with the main image to produce
        # a JPEG.
        mask = Pixmap(self.document, soft_mask_xref)
        return Pixmap(pixmap, mask).tobytes(PYMUPDF_JPEG)

    def _get_native_crop(
        self,
        xref: int,
        image_rect: Rect,
        target: Rect
    ) -> bytes:
        """Crop a region from a larger, axis-aligned PDF image.

        Input:
            xref: The PDF image's xref number.
            image_rect: The bounding box of the PDF image in page coordinates.
            target: The bounding box of the Chandra region in page coordinates.

        Output:
            The cropped image data in JPEG format.
        """

        image_bytes = BytesIO(self._image_bytes(xref))
        stream = BytesIO()

        with Image.open(image_bytes) as image:
            left = round(
                (target.x0 - image_rect.x0) / image_rect.width * image.width
            )

            top = round(
                (target.y0 - image_rect.y0) / image_rect.height * image.height
            )

            right = round(
                (target.x1 - image_rect.x0) / image_rect.width * image.width
            )

            bottom = round(
                (target.y1 - image_rect.y0) / image_rect.height * image.height
            )

            image.crop((left, top, right, bottom)).save(
                stream,
                format=PIL_JPEG
            )

        return stream.getvalue()
