"""Convert PDF pages to images and OCR them with a local Ollama model."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Sequence
from logging import basicConfig, DEBUG, INFO, getLogger

from ollama import chat, ResponseError

from rouen_ocr.pdf_to_images import convert_pdf, positive_scale
from rouen_ocr.html_corrections import HtmlCorrections
from rouen_ocr.html_image_retriever import HtmlImageRetriever
from rouen_ocr.html_document import HtmlDocument

logger = getLogger(__name__)

# The OCR model to use for converting images to text.  This model must be
# available to the local Ollama service. IT MUST BE a Chandra OCR 2 model
# because the OCR chain is designed to work with that model's output. If you
# want to use a different model, you must change the OCR chain to work with your
# model's output.
OCR_MODEL = "hf.co/prithivMLmods/Chandra-OCR-2-GGUF:Q4_K_M"

# The document types that can be provided to the OCR model. The default is
# "auto", which lets the model decide the document type.  Other options are
# "magazine", "administrative", and "commercial".
DOCUMENT_TYPES = ("auto", "magazine", "administrative", "commercial")

# Ollama's default context window (2048 tokens) is easily filled by the vision
# tokens of a single high-resolution page, silently truncating the prompt and
# leaving no room for the model to produce OCR text. Raising num_ctx avoids
# this failure at higher --scale values; increase it further for very large
# pages if OCR output is still empty or truncated.
OCR_NUM_CTX = 16384

# The base prompt to provide to the OCR model. This prompt is always provided,
# and additional instructions are added depending on the document type and page
# number.
OCR_BASE_PROMPT = """
OCR this image to HTML, arranged as layout blocks.

Each layout block must be a div with:
- a data-bbox attribute in normalized x0 y0 x1 y1 coordinates from 0 to 1000;
- a data-label attribute describing the block type.

Preserve the natural reading order, paragraphs, headings, lists, tables,
forms, checkboxes, special characters, subscripts, superscripts, and equations.

Use colspan and rowspan to reproduce table structure.
Use <math> with KaTeX-compatible LaTeX for mathematical expressions.
For images and diagrams, provide an accurate description in the alt attribute.
Join wrapped text lines into paragraphs unless a line break is semantically required.

Return only HTML.
Do not use Markdown fences.
Do not add explanations before or after the HTML.
"""


def ocr_prompt(document_type: str = "auto", page_number: int = 1) -> str:
    """Return the OCR prompt for the requested document type and page.

    Input:
        document_type: The type of document to provide to the OCR model.
        page_number: The page number to provide to the OCR model.

    Output:
        The prompt string to provide to the OCR model.
    """
    prompt = OCR_BASE_PROMPT

    if document_type != "auto":
        prompt = f"{OCR_BASE_PROMPT}\nThis is a {document_type}."

    if page_number == 1:
        prompt = f"{prompt}\nThis is the cover page."
    else:
        prompt = (
            f"{prompt}\nThis is page number {page_number}, "
            "start headings at level 2, not level 1."
        )

    return prompt


def build_parser() -> ArgumentParser:
    """Build the command-line parser.

    Output:
        The argument parser.
    """
    parser = ArgumentParser(description="OCR a PDF with Chandra OCR 2.")

    parser.add_argument(
        "input_pdf",
        type=Path,
        help="PDF file to OCR"
    )

    parser.add_argument(
        "output_text",
        type=Path,
        help="combined UTF-8 HTML output"
    )

    parser.add_argument(
        "--images-dir",
        type=Path,
        help="directory for rendered PNG files (default: <output>-pages)",
    )

    parser.add_argument(
        "--scale",
        type=positive_scale,
        default=4,
        help="PDF render scale (default: 4, 288 DPI)",
    )

    parser.add_argument(
        "--document-type",
        choices=DOCUMENT_TYPES,
        default="auto",
        help="document type to provide to OCR (default: auto)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debugging information",
    )

    return parser


def default_images_dir(output_text: Path) -> Path:
    """Return the default directory for pages rendered for *output_text*.

    Input:
        output_text: The path to the output file.

    Output:
        The path to the directory that will contain pages images.
    """
    return output_text.with_name(f"{output_text.stem}-pages")


def ocr_image(
    image_path: Path,
    document_type: str = "auto",
    page_number: int = 1,
) -> str:
    """Return the HTML portion of Chandra OCR 2's output for one image.

    Input:
        image_path: Path to a PNG file of one PDF page.

    Output:
        HTML fragment containing the OCRed text for that page.
    """
    try:
        result = chat(
            model=OCR_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": ocr_prompt(document_type, page_number),
                    "images": [image_path],
                }
            ],
            options={
                "temperature": 0.0,
                "top_p": 0.1,
                "num_ctx": OCR_NUM_CTX,
                "num_predict": 12384,
                "repeat_penalty": 1.0,
                "seed": 0,
            },
            think=False,
        )
    except ResponseError as error:
        raise ValueError(f"Ollama request failed: {error.error}") from error

    if not result.message or not result.message.content:
        raise ValueError("Ollama response did not contain any content")

    return result.message.content


def html_document(page_fragments: Sequence[str]) -> HtmlDocument:
    """Build one HTML document containing the OCR results for all pages.

    Input:
        page_fragments: A sequence of HTML fragments, one per page.

    Output:
        A complete HTML document containing all pages, each wrapped in a
        ``section`` element with a ``data-page-number`` attribute.
    """
    html = HtmlDocument("")

    for number, fragment in enumerate(page_fragments, start=1):
        html.append_page(fragment, number)

    return html


def show_progress(stage: str, completing: int, total: int) -> None:
    """Print the current progress for a conversion stage."""
    print(f"{stage}: page {completing} of {total}", flush=True)


def show_progress_rendering(completing: int, total: int) -> None:
    """Print the current progress for rendering pages.

    Input:
        completing: The number of pages rendered so far.
        total: The total number of pages to render.
    """
    show_progress("Rendering", completing, total)


def show_progress_replacing(replacing: int, total: int) -> None:
    """Print the current progress for replacing images in HTML.

    Input:
        replacing: The number of images replaced so far.
        total: The total number of images to replace.
    """
    show_progress("Replacing images", replacing, total)


def convert_pdf_to_text(
    input_pdf: Path,
    output_text: Path,
    images_dir: Path,
    scale: int = 4,
    document_type: str = "auto",
) -> int:
    """Render *input_pdf*, OCR each page, and write one HTML file to
    *output_text*.

    The named model must already be available to the local Ollama service.

    Input:
        input_pdf: Path to the PDF file to OCR.
        output_text: Path to the output HTML file.
        images_dir: Directory to store the rendered PNG files.
        scale: Render scale for the PDF pages (default: 4, 288 DPI).
        document_type: Document type for the OCR model (default: auto).

    Output:
        The number of pages OCRed.
    """

    logger.debug(
        f"Converting {input_pdf} to {output_text} with images in {images_dir}, "
        f"scale {scale}, document type {document_type}"
    )

    # Render the PDF pages to PNG files.
    page_count = convert_pdf(
        input_pdf,
        images_dir,
        scale,
        show_progress_rendering,
    )

    # OCR each page and collect the HTML fragments.
    page_text = []
    for number in range(1, page_count + 1):
        logger.info(f"OCRizing page {number} of {page_count}")

        ocr_output = ocr_image(
            images_dir / f"page-{number:04d}.png",
            document_type,
            number,
        )

        logger.debug(f"Page {number} OCR output:\n{ocr_output}")

        page_text.append(ocr_output)

    # Make an HTML document containing all pages, each wrapped in a ``section``
    # element with a ``data-page-number`` attribute.
    html = html_document(page_text)

    # Ensure the output directory exists.
    output_text.parent.mkdir(parents=True, exist_ok=True)

    # Replace the images in the HTML fragments with data URI.
    image_retriever = (HtmlImageRetriever(html)
        .replace_images(input_pdf, show_progress_replacing)
        .show_largest_image_on_cover()
    )

    corrected = HtmlCorrections(image_retriever).correct()

    # Write the combined HTML document to the output file.
    output_text.write_text(str(corrected), encoding="utf-8")

    return page_count


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PDF-to-text command.

    Input:
        argv: Optional list of command-line arguments. If None, uses sys.argv.

    Output:
        Exit code: 0 for success, non-zero for failure.
    """
    args = build_parser().parse_args(argv)

    basicConfig(
        level=DEBUG if args.debug else INFO,
        format="%(levelname)s(%(name)s): %(message)s",
    )

    images_dir = args.images_dir or default_images_dir(args.output_text)
    logger.debug(f"Using images directory: {images_dir}")

    try:
        page_count = convert_pdf_to_text(
            args.input_pdf,
            args.output_text,
            images_dir,
            args.scale,
            args.document_type,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        raise SystemExit(f"error: {error}") from error

    logger.info(f"OCRed {page_count} page(s) to {args.output_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
