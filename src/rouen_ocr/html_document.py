"""HTML document class."""

from __future__ import annotations
from pydoc import html
from typing import Self

from bs4 import BeautifulSoup

from rouen_ocr.html_work import HtmlWork

STYLSHEET = """
:root {
  --primary-color: #c9182b;       /* Rouge identitaire / accent */
  --primary-dark: #960f1e;
  --secondary-color: #1e293b;     /* Texte principal */
  --text-muted: #64748b;          /* Métadonnées & légendes */
  --bg-body: #f8fafc;             /* Fond neutre et doux */
  --bg-surface: #ffffff;          /* Fond des sections de lecture */
  --border-color: #e2e8f0;
  
  --font-family-base: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-family-serif: Georgia, "Times New Roman", Cambria, serif;
  
  --shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.08);
  --radius-sm: 8px;
  --radius-md: 14px;
}

/* Réinitialisation et boîte */
*, *::before, *::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  padding: 1.5rem 1rem;
  font-family: var(--font-family-base);
  font-size: 1.0625rem; /* ~17px pour une lecture confortable */
  line-height: 1.5;
  color: var(--secondary-color);
  background-color: var(--bg-body);
  -webkit-font-smoothing: antialiased;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Conteneur de section linéaire */
section[data-page-number] {
  width: 100%;
  max-width: 760px; /* Largeur optimale de lecture (65 à 75 caractères/ligne) */
  background-color: var(--bg-surface);
  margin-bottom: 2.5rem;
  padding: 2.5rem 2rem;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-color);
  position: relative;
}

/* Indicateur discret du numéro de page d'origine */
section[data-page-number]::before {
  content: "Page " attr(data-page-number);
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  background: var(--bg-body);
  padding: 0.2rem 0.6rem;
  border-radius: 20px;
}

/* Titres */
h1 {
  font-size: 2.4rem;
  font-weight: 800;
  color: var(--primary-color);
  line-height: 1.15;
  margin: 1.5rem 0 1rem 0;
  letter-spacing: -0.02em;
}

h2 {
  font-size: 1.65rem;
  font-weight: 700;
  color: var(--secondary-color);
  line-height: 1.25;
  margin: 1.5rem 0 1rem 0;
  border-left: 4px solid var(--primary-color);
  padding-left: 0.75rem;
}

h3 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--secondary-color);
  margin: 2rem 0 1rem 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

/* Paragraphes */
p {
  margin: 0 0 1.25rem 0;
}

/* Liens */
a {
  color: var(--primary-color);
  text-decoration: underline;
  text-underline-offset: 3px;
  font-weight: 500;
  transition: color 0.2s ease;
}

a:hover, a:focus {
  color: var(--primary-dark);
}

/* Images responsives */
img {
  max-width: 100%;
  height: auto;
  display: block;
  margin: 1.75rem auto;
  border-radius: var(--radius-sm);
  box-shadow: var(--shadow-sm);
}

/* Adaptations écrans mobiles */
@media (max-width: 640px) {
  body {
    padding: 0.75rem 0.5rem;
    font-size: 1rem;
  }

  section[data-page-number] {
    padding: 1.75rem 1.25rem;
    margin-bottom: 1.5rem;
    border-radius: var(--radius-sm);
  }

  h1 { font-size: 1.9rem; }
  h2 { font-size: 1.35rem; }
  h3 { font-size: 1.1rem; }
}
"""


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
            '<!doctype html>\n<html><head>'
            '<meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '</head>'
            f'<body>{html_body_content}</body></html>',
            "html.parser"
        )

        if self.soup.head:
            # Add the stylesheet to the <head> tag
            style_tag = self.soup.new_tag("style")
            style_tag.string = STYLSHEET
            
            self.soup.head.append(style_tag)

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
