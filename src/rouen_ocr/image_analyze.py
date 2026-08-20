"""Analyze an image."""

from __future__ import annotations

from logging import getLogger

from ollama import chat, ResponseError

logger = getLogger(__name__)

# The model to use for analyzing images.
ALT_MODEL = "huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF:Q8_0"

# The number of context tokens to provide to the model. This is the maximum
# number of tokens that can be provided to the model in a single request. The
# model will use as many tokens as it can, up to this limit, to generate the
# output. If the input is too long, the model will truncate it.
ALT_NUM_CTX = 16384

# The base prompt to provide to the model. This prompt is always provided.
ANA_BASE_PROMPT = """
Analyze the provided image and determine its type.

There can be only the following types:
- photo: a photograph of a real-world scene, object, or person.
- big letter: the image is mainly a large decorative letter at the beginning of a paragraph or section, often used in illuminated manuscripts and other historical documents.
- drawing: a drawing is a visual element that is not part of the original content of the document, but is instead a result of the scanning or OCR process. Drawings can include things like smudges, stains, or other marks on the page, as well as errors introduced by the OCR process itself.

Only return the type of the image, without any other information or explanation.
"""


def analyze_image(image: bytes) -> str:
    """Analyze an image.

    Input:
        image: The image data as bytes.

    Output:
        The analysis of the image.
    """
    logger.info("Analyzing an image")
    try:
        result = chat(
            model=ALT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": ANA_BASE_PROMPT,
                    "images": [image],
                }
            ],
            options={
                "temperature": 0.0,
                "top_p": 0.1,
                "num_ctx": ALT_NUM_CTX,
                "num_predict": 16384,
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
