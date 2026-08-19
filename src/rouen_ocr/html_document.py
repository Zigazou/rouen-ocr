"""HTML document class."""

from __future__ import annotations
from pydoc import html
from typing import Self

from bs4 import BeautifulSoup

from rouen_ocr.html_work import HtmlWork


class HtmlDocument(HtmlWork):
    """A class for representing an HTML document."""

    def __init__(self, html: str | object) -> None:
        """Initialize the HtmlDocument with the given HTML content.

        Input:
            html: The HTML content as a string or an HtmlWork object.
        """
        super().__init__(html)

        self.prepare_document()

    def prepare_document(self) -> Self:
        """Prepare the HTML document for further processing.

        This put the current self.soup content into a proper HTML document
        structure with <html>, <head>, and <body> tags.

        Output:
            Self, for method chaining.
        """
        html_body_content = str(self.soup)

        self.soup = BeautifulSoup(
            f'<!doctype html>\n<html><head><meta charset="utf-8"></head>'
            f'<body>{html_body_content}</body></html>',
            "html.parser"
        )

        return self

    def append_page(self, page_html: str, page_number: int) -> Self:
        """Append a page to the HTML document in the body tag.

        Input:
            page_html: The HTML content of the page.
            page_number: The one-based page number.

        Output:
            Self, for method chaining.
        """

        if self.soup.body:
            section = self.soup.new_tag("section")
            section["data-page-number"] = str(page_number)
            section.append(BeautifulSoup(page_html, "html.parser"))

            self.soup.body.append(section)

        return self
