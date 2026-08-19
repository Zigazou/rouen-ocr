"""Convert PDF pages to images and ALT them with a local Ollama model."""

from __future__ import annotations

from logging import getLogger

from ollama import chat, ResponseError

logger = getLogger(__name__)

# The model to use for generating a textual alternative for an image.
ALT_MODEL = "huggingface.co/mistralai/Ministral-3-3B-Instruct-2512-GGUF:Q8_0"

# The number of context tokens to provide to the model. This is the maximum
# number of tokens that can be provided to the model in a single request. The
# model will use as many tokens as it can, up to this limit, to generate the
# output. If the input is too long, the model will truncate it.
ALT_NUM_CTX = 16384

# The base prompt to provide to the model. This prompt is always provided.
ALT_BASE_PROMPT = """
Génère une alternative textuelle pour l'image fournie.

L'alternative textuelle doit être concise, descriptive et informative.

Elle doit décrire le contenu de l'image de manière à ce qu'une personne qui ne
peut pas voir l'image puisse comprendre ce qu'elle représente.

L'alternative textuelle doit être rédigée en français.

Donne uniquement l'alternative textuelle, sans aucune autre information ni
explication.
"""


def alt_image(image: bytes) -> str:
    """Generate a textual alternative for an image.

    Input:
        image: The image data as bytes.

    Output:
        The textual alternative for the image.
    """
    logger.info("Generating a textual alternative for an image")
    try:
        result = chat(
            model=ALT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": ALT_BASE_PROMPT,
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
