"""Post-process HTML returned by the OCR model."""

from bs4.element import NavigableString, Tag
from typing import Self

from rouen_ocr.html_work import HtmlWork


class HtmlCorrections(HtmlWork):
    """Apply safe structural corrections to OCR-produced HTML.

    OCR responses occasionally contain reasoning text directly inside a page
    ``section`` before the actual HTML elements.  That text is not document
    content, so it must not be kept in the resulting page.  The correction is
    deliberately limited to direct text nodes: text inside elements such as
    paragraphs, headings, captions, or links is always preserved.
    """

    def remove_chandra_divs(self) -> Self:
        """Unwrap ``div`` elements carrying Chandra's ``data-label`` marker.

        Chandra uses these wrappers to annotate detected regions.  The
        annotation is not part of the document markup, but the wrapped nodes
        are, so ``unwrap`` is used instead of removing the element.
        """
        for div in self.soup.find_all("div", attrs={"data-label": True}):
            div.unwrap()

        self.remember("remove_chandra_divs")

        return self

    def increase_heading_levels(self) -> Self:
        """Increase heading level by 1 inside numbered page sections.

        The section tags are inserted by pdf_to_text.py to mark the start of
        each page.  The first page is considered the cover page.
        """
        self.require_step("remove_chandra_divs")

        sections = self.soup.find_all(
            "section",
            attrs={"data-page-number": True}
        )

        for section in sections:
            page_number = section.get("data-page-number")
            if not isinstance(page_number, str) or not page_number.isdigit():
                continue

            page_number = int(page_number)

            # Only increase heading levels for pages after the cover page.
            if page_number == 1:
                continue

            # Works on all heading levels except h6. This may be a problem if
            # the OCR model produces h6 headings, but it is unlikely.
            for heading in section.find_all(["h1", "h2", "h3", "h4", "h5"]):
                level = int(heading.name[1])
                heading.name = f"h{level + 1}"

        self.remember("increase_heading_levels")

        return self

    def remove_unneeded_brs(self) -> Self:
        """When a br tag is followed by a lowercase letter, remove it.

        For small chunks of text, the OCR model sometimes inserts a br tag
        between two lines. On an HTML page, this is usually not needed, and it
        can break the flow of text.  This correction removes br tags that are
        followed by a lowercase letter, which is a strong indication that the br
        tag is not needed.
        """
        self.require_step("remove_chandra_divs")

        for br in self.soup.find_all("br"):
            following = br.next_sibling

            if not isinstance(following, NavigableString):
                continue

            text = following.lstrip()
            if text and text[0].islower():
                previous = br.previous_sibling

                has_preceding_space = (
                    isinstance(previous, NavigableString)
                    and previous
                    and previous[-1].isspace()
                )

                if has_preceding_space or following[:1].isspace():
                    replacement = ""
                else:
                    replacement = " "

                br.replace_with(replacement)

        self.remember("remove_unneeded_brs")

        return self

    def remove_unneeded_ps(self) -> Self:
        """When a p tag is preceded by a comma, merge the consecutive p tags.

        This is a common OCR error when a paragraph is split into two p tags.
        """
        self.require_step("remove_chandra_divs")

        for paragraph in self.soup.find_all("p"):
            while paragraph.get_text().rstrip().endswith(","):
                following = paragraph.next_sibling
                while (
                    isinstance(following, NavigableString) and
                    not following.strip()
                ):
                    following = following.next_sibling

                if not following or getattr(following, "name", None) != "p":
                    break

                if (
                    paragraph.get_text() and
                    not paragraph.get_text()[-1].isspace()
                ):
                    following_text = following.get_text()
                    if following_text and not following_text[0].isspace():
                        paragraph.append(" ")

                if isinstance(following, Tag):
                    for child in list(following.contents):
                        paragraph.append(child.extract())

                following.decompose()

        self.remember("remove_unneeded_ps")

        return self

    def set_title(self, title: str) -> Self:
        """Set the title of the HTML document.

        This method sets the title of the HTML document, which is used by
        browsers and other tools to identify the document.  If the document
        already has a title, it is replaced.  If it does not have a title, one
        is added.

        Input:
            title: The title to set for the HTML document.
        """
        head = self.soup.head
        if head is None:
            head = self.soup.new_tag("head")
            self.soup.insert(0, head)

        title_tag = head.title
        if title_tag is None:
            title_tag = self.soup.new_tag("title")
            head.append(title_tag)

        title_tag.string = title

        return self

    def remove_footers_and_headers(self) -> Self:
        """Remove the footer and header from the HTML document.

        This method removes the footer and header from the HTML document, which
        are not part of the document content.  The footer and header are
        identified by their data-label attributes, which are added by the OCR
        model.
        """
        footers_headers = self.soup.find_all(
            "div",
            attrs={"data-label": True}
        )
        
        for div in footers_headers:
            if div.get("data-label") in ["Page-Header", "Page-Footer"]:
                div.decompose()

        self.remember("remove_footers_and_headers")

        return self

    def set_title_from_first_heading(self) -> Self:
        """Set the title of the HTML document from the first heading.

        This method sets the title of the HTML document to the text of the
        first heading (h1, h2, h3, h4, h5, or h6) found in the document.  If no
        heading is found, the title is not changed.
        """
        first_heading = self.soup.find("h1")

        if first_heading and first_heading.get_text():
            self.set_title(first_heading.get_text())

        return self

    def correct(self) -> Self:
        """Apply all HTML corrections in the proper order."""
        self.remove_footers_and_headers()
        self.remove_chandra_divs()
        self.increase_heading_levels()
        self.remove_unneeded_brs()
        self.remove_unneeded_ps()
        self.set_title_from_first_heading()

        return self
