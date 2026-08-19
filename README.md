# Rouen OCR

Python 3.11 project for OCR-related tooling.

## Setup

Create an environment and install the project with its development tools:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Quality checks

```bash
ruff check .
pytest
```

## Convert a PDF to images

Render every PDF page to a PNG image with PyPdfium. `--scale` controls the
rendering resolution: `1` corresponds to PDF's native 72 DPI, while `4.1667`
is approximately 300 DPI.

```bash
pdf-to-images document.pdf output-pages --scale 4.1667
```

The output directory is created when needed. Page files are named
`page-0001.png`, `page-0002.png`, and so on.

The module can also be executed directly:

```bash
python -m rouen_ocr.pdf_to_images document.pdf output-pages --scale 2
```

## OCR a PDF with Chandra OCR 2 via Ollama

Install the Python dependencies, start Ollama locally, and pull a
vision-capable Chandra OCR 2 model (for example,
`ollama pull fredrezones55/chandra-ocr-2`).
The command sends each rendered PNG page individually to the local Ollama
service. It produces a UTF-8 HTML document containing
one `<section>` per page, and keeps the intermediary PNG files (by default,
beside the HTML file in `<output>-pages`). Reasoning and non-HTML model output
are excluded from the file. When the document is ambiguous, the OCR model is
also given the Rouen-specific terms in `src/rouen_ocr/assets/rouen-words.md` to
prefer their exact spelling, accents, capitalization, and wording.

```bash
pdf-to-text document.pdf document.html
```

Use `--model` to select the Ollama model identifier. Use
`--images-dir` to choose another directory for the rendered pages, and
`--scale` to change rendering resolution.
Use `--document-type` to tell the model whether the document is `magazine`, `administrative`, or `commercial`; the default is `auto`.

Higher `--scale` values produce more vision tokens per page. If Ollama's
context window is too small, the model accepts the image but returns empty or
truncated OCR text; `OCR_NUM_CTX` in `pdf_to_text.py` raises the context window
to cover this. Increase it further if OCR still fails on very large pages.

