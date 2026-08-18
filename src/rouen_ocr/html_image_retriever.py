"""HTML Image Retriever class.

This class only works with HTML that has been returned by the Chandra OCR 2
model, which uses div tags with a data-label attribute set to "Image" to
identify images. The HTML must not have been modified by any other process, such
as the HTML corrections applied by the HtmlCorrections class.

The data-bbox attribute of the div tag contains the bounding box of the image.
"""

from rouen_ocr.html_work import HtmlWork
from rouen_ocr.image_bbox import ImageBBox


class HtmlImageRetriever(HtmlWork):
    def find_images(self) -> list[ImageBBox]:
        """Find all images in the HTML document or fragment.

        Images are identified by a div tag with an attribute data-label set to
        "Image", i.e. `<div data-bbox="78 12 146 83" data-label="Image">`.

        Output:
            A list of all ImageBBox instances in the HTML.

        """
        divs = self.soup.find_all("div", {"data-label": "Image"})
        bboxes = []
        for div in divs:
            bbox_str = div.get("data-bbox")

            if isinstance(bbox_str, str):
                try:
                    bboxes.append(ImageBBox.from_chandra_attribute(bbox_str))
                except ValueError:
                    # Ignore any invalid data-bbox attribute, but log a warning.
                    print(f"Warning: Invalid data-bbox attribute: {bbox_str}")
                    pass

        return bboxes
