"""Class holding the bounding box of an image in Chandra coordinates (0-1000).
The Chandra OCR 2 model returns the bounding box of images in the HTML output as
a string of four integers in the range [0, 1000], separated by spaces, in the
order x0 y0 x1 y1.

Notes:
- The coordinates are relative to the image size, with (0, 0) being the
  top-left corner and (1000, 1000) being the bottom-right corner.
- All coordinates are inclusive.
- The width of the bounding box is x1 - x0 and the height is y1 - y0.

The bounding box is used to identify the location of the image in the original
PDF page, and can be translated to pixel coordinates based on the size of the
rendered image. The class provides methods to translate the coordinates to pixel
values and to generate a unique identifier for the bounding box based on its
coordinates.
"""

from typing import Self


class ImageBBox:
    def __init__(
        self,
        x0_1000: int,
        y0_1000: int,
        x1_1000: int,
        y1_1000: int
    ) -> None:
        """Initialize an ImageBBox with coordinates in the range [0, 1000].

        Input:
            x0_1000: The x-coordinate of the top-left corner (0-1000).
            y0_1000: The y-coordinate of the top-left corner (0-1000).
            x1_1000: The x-coordinate of the bottom-right corner (0-1000).
            y1_1000: The y-coordinate of the bottom-right corner (0-1000).

        Raises:
            ValueError: If any of the coordinates are outside the range
                [0, 1000].
        """
        if not all(
            value >= 0 and value <= 1000
            for value in (x0_1000, y0_1000, x1_1000, y1_1000)
        ):
            raise ValueError(
                "Invalid Chandra attribute values: "
                f"{(x0_1000, y0_1000, x1_1000, y1_1000)}"
            )

        self.x0_1000 = x0_1000
        self.y0_1000 = y0_1000
        self.x1_1000 = x1_1000
        self.y1_1000 = y1_1000

    def translate_coordinates(
        self,
        image_width: int,
        image_height: int
    ) -> tuple[int, int, int, int]:
        """Translate the coordinates to pixel values based on the image size.

        Input:
            image_width: The width of the image in pixels.
            image_height: The height of the image in pixels.

        Output:
            A tuple of translated coordinates (x0, y0, x1, y1) in pixels.
        """
        assert image_width > 0, "Image width must be strictly positive."
        assert image_height > 0, "Image height must be strictly positive."

        x0 = round(self.x0_1000 * image_width / 1000)
        y0 = round(self.y0_1000 * image_height / 1000)
        x1 = round(self.x1_1000 * image_width / 1000)
        y1 = round(self.y1_1000 * image_height / 1000)

        return (x0, y0, x1, y1)

    def id(self, base: str) -> str:
        """Return a unique identifier for the bounding box.

        Input:
            base: A base string to prepend to the identifier.

        Output:
            A unique identifier string for the bounding box.
        """
        return (
            f"{base}-"
            f"{self.x0_1000}-{self.y0_1000}-"
            f"{self.x1_1000}-{self.y1_1000}"
        )

    @classmethod
    def from_chandra_attribute(cls, attribute: str) -> Self:
        """Create an ImageBBox from a Chandra image attribute string."""
        # The attribute string is in the format "x y width height" and must
        # contain exactly four integer values.
        try:
            return cls(*map(int, attribute.split()))
        except:
            raise ValueError(f"Invalid Chandra attribute string: {attribute}")
