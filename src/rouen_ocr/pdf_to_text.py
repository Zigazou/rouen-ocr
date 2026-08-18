"""Convert PDF pages to images and OCR them with a local Ollama model."""

from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
from typing import Sequence

from ollama import chat, ResponseError

from rouen_ocr.pdf_to_images import convert_pdf, positive_scale
from rouen_ocr.html_corrections import HtmlCorrections


# The OCR model to use for converting images to text.  This model must be
# available to the local Ollama service. IT MUST BE a Chandra OCR 2 model
# because the OCR chain is designed to work with that model's output. If you
# want to use a different model, you must change the OCR chain to work with your
# model's output.
OCR_MODEL = "fredrezones55/chandra-ocr-2:latest"

# The document types that can be provided to the OCR model. The default is
# "auto", which lets the model decide the document type.  Other options are
# "magazine", "administrative", and "commercial".
DOCUMENT_TYPES = ("auto", "magazine", "administrative", "commercial")

# The base prompt to provide to the OCR model. This prompt is always provided,
# and additional instructions are added depending on the document type and page
# number.
OCR_BASE_PROMPT = f"""OCR this image.
Return ONLY HTML.
Do not use Markdown fences.
Do not add any explanation before or after the HTML.
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
        default=2,
        help="PDF render scale (default: 2, 144 DPI)",
    )

    parser.add_argument(
        "--document-type",
        choices=DOCUMENT_TYPES,
        default="auto",
        help="document type to provide to OCR (default: auto)",
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
            options={"temperature": 0},
            think=False,
        )
    except ResponseError as error:
        raise ValueError(f"Ollama request failed: {error.error}") from error

    if not result.message or not result.message.content:
        raise ValueError("Ollama response did not contain any content")

    return result.message.content


def html_document(page_fragments: Sequence[str]) -> str:
    """Build one HTML document containing the OCR results for all pages.

    Input:
        page_fragments: A sequence of HTML fragments, one per page.

    Output:
        A complete HTML document containing all pages, each wrapped in a
        ``section`` element with a ``data-page-number`` attribute.
    """
    html_body_content = "\n".join(
        f'<section data-page-number="{number}">\n{fragment}\n</section>'
        for number, fragment in enumerate(page_fragments, start=1)
    )

    html_content = (
        "<!doctype html>\n<html>\n<head><meta charset=\"utf-8\"></head>\n"
        f"<body>\n{html_body_content}\n</body>\n</html>\n"
    )

    corrected = HtmlCorrections(html_content).correct()

    return str(corrected)


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


def convert_pdf_to_text(
    input_pdf: Path,
    output_text: Path,
    images_dir: Path,
    scale: int = 2,
    document_type: str = "auto",
) -> int:
    """Render *input_pdf*, OCR each page, and write one HTML file to
    *output_text*.

    The named model must already be available to the local Ollama service.

    Input:
        input_pdf: Path to the PDF file to OCR.
        output_text: Path to the output HTML file.
        images_dir: Directory to store the rendered PNG files.
        scale: Render scale for the PDF pages (default: 2, 144 DPI).
        document_type: Document type for the OCR model (default: auto).

    Output:
        The number of pages OCRed.
    """
    page_count = convert_pdf(
        input_pdf,
        images_dir,
        scale,
        show_progress_rendering,
    )

    page_text = []

    for number in range(1, page_count + 1):
        show_progress("OCRizing", number, page_count)

        page_text.append(
            ocr_image(
                images_dir / f"page-{number:04d}.png",
                document_type,
                number,
            )
        )

    output_text.parent.mkdir(parents=True, exist_ok=True)

    output_text.write_text(html_document(page_text), encoding="utf-8")

    return page_count


def main(argv: Sequence[str] | None = None) -> int:
    """Run the PDF-to-text command.

    Input:
        argv: Optional list of command-line arguments. If None, uses sys.argv.

    Output:
        Exit code: 0 for success, non-zero for failure.
    """
    args = build_parser().parse_args(argv)

    images_dir = args.images_dir or default_images_dir(args.output_text)

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

    print(f"OCRed {page_count} page(s) to {args.output_text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
