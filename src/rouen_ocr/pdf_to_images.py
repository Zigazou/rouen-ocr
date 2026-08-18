"""Render PDF pages as PNG images using PyPdfium."""

from __future__ import annotations

from argparse import ArgumentParser, ArgumentTypeError
from collections.abc import Callable
from pathlib import Path
from typing import Sequence
from pypdfium2 import PdfDocument


def positive_scale(value: str) -> int:
    """Return a strictly positive render scale for argparse.

    Input:
        value: The string value to convert to an int.

    Returns:
        int: The converted positive scale value.

    Raises:
        argparse.ArgumentTypeError: If the value is not a valid positive int.
    """
    try:
        scale = int(value)
    except ValueError as error:
        raise ArgumentTypeError("scale must be a number") from error

    if scale <= 0:
        raise ArgumentTypeError("scale must be greater than zero")

    return scale


def build_parser() -> ArgumentParser:
    """Build the command-line parser.

    Output:
        The argument parser.
    """
    parser = ArgumentParser(
        description="Render every page of a PDF as a PNG image using PyPdfium."
    )

    parser.add_argument(
        "input_pdf",
        type=Path,
        help="PDF file to render"
    )

    parser.add_argument(
        "output_dir",
        type=Path,
        help="directory for PNG files"
    )

    parser.add_argument(
        "--scale",
        type=positive_scale,
        default=1.0,
        help="render scale (default: 1; 4 is 288 DPI)",
    )

    return parser


def convert_pdf(
    input_pdf: Path,
    output_dir: Path,
    scale: int = 2,
    progress_callback: Callable[[int, int], None] | None = None,
) -> int:
    """Render *input_pdf* pages to *output_dir* and return the page count."""
    if not input_pdf.is_file():
        raise FileNotFoundError(f"PDF file does not exist: {input_pdf}")
    if scale <= 0:
        raise ValueError("scale must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    document = PdfDocument(input_pdf)
    page_count = len(document)
    try:
        for page_number in range(page_count):
            if progress_callback is not None:
                progress_callback(page_number + 1, page_count)

            page = document[page_number]
            try:
                bitmap = page.render(scale=scale)
                try:
                    image = bitmap.to_pil()
                    image.save(
                        output_dir / f"page-{page_number + 1:04d}.png",
                        "PNG"
                    )
                finally:
                    bitmap.close()
            finally:
                page.close()
    finally:
        document.close()

    return page_count


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PDF-to-images command.
    
    Input:
        argv: Optional list of command-line arguments. If None, uses sys.argv.

    Output:
        Exit code: 0 for success, non-zero for failure.
    """
    args = build_parser().parse_args(argv)

    try:
        page_count = convert_pdf(args.input_pdf, args.output_dir, args.scale)
    except (FileNotFoundError, ValueError, OSError) as error:
        raise SystemExit(f"error: {error}") from error

    print(f"Rendered {page_count} page(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
