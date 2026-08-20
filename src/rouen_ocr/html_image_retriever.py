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
from collections.abc import Callable
from logging import getLogger
from pathlib import Path
from typing import Self

from pymupdf import Document, IRect, Matrix, Pixmap, Rect, csRGB

from rouen_ocr.bbox import BBox
from rouen_ocr.html_work import HtmlWork
from rouen_ocr.image_analyze import analyze_image
from rouen_ocr.textual_alternative import alt_image

PYMUPDF_JPEG = "jpg"

logger = getLogger(__name__)

class HtmlImageRetriever(HtmlWork):
    def __init__(self, html: str | object) -> None:
        """Initialize the retriever with the HTML document or fragment.

        Input:
            html: The HTML document or fragment to process. It can be a string
                or a BeautifulSoup object.
        """
        super().__init__(html)

        self.document = None
        self.images = {}
        self.bboxes = []
        self.find_images()

    def find_images(self) -> None:
        """Find all images in the HTML document or fragment.

        Images are identified by a div tag with an attribute data-label set to
        "Image", i.e. `<div data-bbox="78 12 146 83" data-label="Image">`.
        """

        # Find all section tags with a data-page-number attribute.
        sections = self.soup.find_all(
            "section",
            attrs={"data-page-number": True}
        )

        self.bboxes = []
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

                self.bboxes.append(
                    BBox.from_chandra_attribute(bbox_str, page_number)
                )

    def show_largest_image_on_cover(self) -> Self:
        """Show the largest image on the cover page of the document.

        This method is intended for debugging purposes. It displays the largest
        image found on the first page of the document using the default image
        viewer.
        """
        if self.document is None:
            raise RuntimeError("PDF document is not open.")

        # Find the first page (section data-page-number="1").
        first_page_section = self.soup.find(
            "section",
            {"data-page-number": "1"}
        )

        # Insert the image at the beginning of the first page section.
        if first_page_section is None:
            logger.warning("No section found for the cover page.")
            return self

        try:
            page = self.document[0]
        except IndexError as error:
            raise ValueError(
                "PDF does not contain a cover page."
            ) from error

        image_infos = page.get_image_info(xrefs=True)

        # Find the largest image on the cover page.
        largest_image = None
        largest_area = 0
        for info in image_infos:
            image_rect = Rect(info["bbox"])
            area = image_rect.get_area()
            if area > largest_area:
                largest_area = area
                largest_image = info

        if largest_image is None:
            logger.warning("No image found on the cover page.")
            return self

        xref = largest_image.get("xref", 0)

        if xref <= 0:
            logger.warning("No valid image found on the cover page.")
            return self

        image_bytes = self._image_bytes(xref)
        textual_alternative = alt_image(image_bytes)

        # Insert the image into the HTML for display.
        data_uri = (
            "data:image/jpeg;base64,"
            f"{b64encode(image_bytes).decode('utf-8')}"
        )

        img_tag = self.soup.new_tag(
            "img",
            src=data_uri,
            alt=textual_alternative
        )

        first_page_section.insert(0, img_tag)

        # Remove other images on the cover page to avoid clutter.
        for div in first_page_section.find_all("div", {"data-label": "Image"}):
            div.decompose()

        return self

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
        
        for bbox in self.bboxes:
            div = self.soup.find(
                "div",
                {"data-bbox": bbox.to_chandra_attribute()}
            )

            if div is None:
                continue

            # Find the corresponding image bytes for this bounding box.
            image_bytes = self.images.get(bbox.id(), None)
            if image_bytes is None:
                # Remove the div if no image was found for this bounding box.
                div.decompose()
                continue

            # Remove the div if the image is a big letter.
            if analyze_image(image_bytes) == "big letter":
                div.decompose()
                continue

            # Replace the div tag with an img tag containing the data URI of the
            # extracted image.
            data_uri = (
                "data:image/jpeg;base64,"
                f"{b64encode(image_bytes).decode('utf-8')}"
            )

            textual_alternative = alt_image(image_bytes)

            div.clear()

            img = self.soup.new_tag(
                "img",
                src=data_uri,
                alt=textual_alternative
            )

            div.append(img)

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
            ValueError: If ``page_number`` is out of range, ``render_scale`` is
                not strictly positive, or ``match_threshold`` is not in the
                range (0, 1].
            RuntimeError: If the PDF document is not open.
        """
        if self.document is None:
            raise RuntimeError("PDF document is not open.")

        if page_number < 1 or page_number > len(self.document):
            raise ValueError(
                f"page_number {page_number} is out of range. "
                f"PDF has {len(self.document)} pages."
            )

        if render_scale <= 0:
            raise ValueError(
                f"render_scale {render_scale} must be strictly positive."
            )

        if match_threshold <= 0 or match_threshold > 1:
            raise ValueError(
                f"match_threshold {match_threshold} must be in the range (0, 1]."
            )

        try:
            page = self.document[page_number - 1]
        except IndexError as error:
            raise ValueError(
                f"PDF does not contain page {page_number}."
            ) from error

        image_infos = page.get_image_info(xrefs=True)

        for bbox in [bbox for bbox in self.bboxes if bbox.page == page_number]:
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

            self.images[bbox_id] = self._pixmap_to_jpeg(pixmap)

    @staticmethod
    def _to_rgb_pixmap(pixmap: Pixmap) -> Pixmap:
        """Convert a CMYK pixmap to RGB and return other pixmaps unchanged."""
        if pixmap.colorspace is not None and pixmap.colorspace.n == 4:
            return Pixmap(csRGB, pixmap)

        return pixmap

    @classmethod
    def _pixmap_to_jpeg(cls, pixmap: Pixmap) -> bytes:
        """Encode a pixmap as JPEG, converting CMYK before encoding."""
        return cls._to_rgb_pixmap(pixmap).tobytes(PYMUPDF_JPEG)

    def _pdf_rect(self, page_rect: Rect, bbox: BBox) -> Rect:
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
        """Return whether ``outer`` completely contains ``inner``.

        Input:
            outer: The outer rectangle.
            inner: The inner rectangle.

        Output:
            True if ``outer`` completely contains ``inner``, False otherwise.
        """
        return (
            outer.x0 <= inner.x0 and outer.y0 <= inner.y0 and
            outer.x1 >= inner.x1 and outer.y1 >= inner.y1
        )

    def _is_axis_aligned(self, info: dict) -> bool:
        """Return whether a PDF image can be cropped without rotation handling.

        Input:
            info: The dictionary returned by PyMuPDF's get_image_info().

        Output:
            True if the PDF image can be cropped without rotation handling,
            False otherwise.
        """
        transform = info.get("transform")

        if transform is None:
            return True

        return (transform[1] == 0 and transform[2] == 0)

    def _image_bytes(self, xref: int) -> bytes:
        """Return image data, reconstructing a soft mask when one is present.

        Input:
            xref: The PDF image's xref number.

        Output:
            The image data in JPEG format.

        Raises:
            RuntimeError: If the PDF document is not open.
        """
        if self.document is None:
            raise RuntimeError("PDF document is not open.")

        return self._pixmap_to_jpeg(Pixmap(self.document, xref))

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

        if self.document is None:
            raise RuntimeError("PDF document is not open.")

        pixmap = self._to_rgb_pixmap(Pixmap(self.document, xref))
        left, top, right, bottom = map(round, [
            (target.x0 - image_rect.x0) / image_rect.width * pixmap.width,
            (target.y0 - image_rect.y0) / image_rect.height * pixmap.height,
            (target.x1 - image_rect.x0) / image_rect.width * pixmap.width,
            (target.y1 - image_rect.y0) / image_rect.height * pixmap.height,
        ])
        clip = IRect(
            pixmap.x + left,
            pixmap.y + top,
            pixmap.x + right,
            pixmap.y + bottom,
        )
        cropped = Pixmap(pixmap, pixmap.width, pixmap.height, clip)

        return cropped.tobytes(PYMUPDF_JPEG)
