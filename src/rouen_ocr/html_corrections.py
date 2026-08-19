"""Post-process HTML returned by the OCR model."""

from bs4.element import NavigableString, Tag
from typing import Self

from rouen_ocr.html_work import HtmlWork
from rouen_ocr.bbox import BBox


class HtmlCorrections(HtmlWork):
    """Apply safe structural corrections to OCR-produced HTML.

    OCR responses occasionally contain reasoning text directly inside a page
    ``section`` before the actual HTML elements. That text is not document
    content, so it must not be kept in the resulting page. The correction is
    deliberately limited to direct text nodes: text inside elements such as
    paragraphs, headings, captions, or links is always preserved.
    """

    def group_nearby_text_divs(self) -> Self:
        """Place nearby ``div`` elements containing text next to each other.

        Proximity of text ``div`` is determined based on the data-bbox
        attribute, which contains the bounding box of the text in the original
        PDF.

        Text ``div`` elements are identified by the presence of the data-label
        attribute of value "Text".

        If two ``div`` elements are close enough, the later one is moved
        directly after the earlier one. This correction is useful for OCR
        responses that interleave unrelated regions between parts of the same
        text, which can break its reading order.
        """
        self.must_not_have("remove_chandra_divs")

        # Pages are divided into sections.
        pages = self.soup.find_all(
            "section",
            attrs={"data-page-number": True}
        )

        # For each page, find all text divs and group them if they are close
        # enough.
        for page in pages:
            # Find all text divs in the page.
            text_divs = page.find_all(
                "div",
                attrs={
                    "data-label": "Text",
                    "data-bbox": True
                }
            )

            divs_with_bboxes: list[tuple[Tag, BBox]] = []
            for text_div in text_divs:
                bbox_attribute = text_div.get("data-bbox")
                if not isinstance(bbox_attribute, str):
                    continue

                try:
                    bbox = BBox.from_chandra_attribute(bbox_attribute)
                except ValueError:
                    # One malformed region must not prevent corrections from
                    # being applied to the rest of the page.
                    continue

                divs_with_bboxes.append((text_div, bbox))

            for text_div, bbox in divs_with_bboxes:
                following_divs = (
                    (candidate_div, candidate_bbox)
                    for candidate_div, candidate_bbox in divs_with_bboxes
                    if bbox.is_before(candidate_bbox)
                )
                closest = min(
                    following_divs,
                    key=lambda candidate: bbox.smallest_distance_to_border(
                        candidate[1]
                    ),
                    default=None
                )

                if closest is None:
                    continue

                closest_div, closest_bbox = closest
                if bbox.smallest_distance_to_border(closest_bbox) < 10:
                    text_div.insert_after(closest_div.extract())

        self.remember("group_nearby_text_divs")

        return self

    def remove_chandra_divs(self) -> Self:
        """Unwrap ``div`` elements carrying Chandra's ``data-label`` marker.

        Chandra uses these wrappers to annotate detected regions. The
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
        each page. The first page is considered the cover page.
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
        can break the flow of text. This correction removes br tags that are
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
        """Merge consecutive p tags when this is necessary.

        Two consecutive p tags must be merged if:

        - The first p tag ends with a comma, and the second p tag starts with a
          lowercase letter.
        - The first p tag ends without a dot, and the second p tag starts with a
          lowercase letter.

        This is a common OCR error when a paragraph is split into two p tags.
        """
        self.require_step("remove_chandra_divs")

        for paragraph in self.soup.find_all("p"):
            while True:
                following = paragraph.next_sibling
                while (
                    isinstance(following, NavigableString) and
                    not following.strip()
                ):
                    following = following.next_sibling

                if not following or getattr(following, "name", None) != "p":
                    break

                paragraph_text = paragraph.get_text().rstrip()
                following_text = following.get_text().lstrip()
                starts_with_lowercase = (
                    bool(following_text) and following_text[0].islower()
                )
                ends_with_comma = paragraph_text.endswith(",")
                ends_without_period = (
                    bool(paragraph_text) and not paragraph_text.endswith(".")
                )

                if not starts_with_lowercase or not (
                    ends_with_comma or ends_without_period
                ):
                    break

                if (
                    paragraph.get_text() and
                    not paragraph.get_text()[-1].isspace()
                ):
                    untrimmed_following_text = following.get_text()
                    if (
                        untrimmed_following_text and
                        not untrimmed_following_text[0].isspace()
                    ):
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
        browsers and other tools to identify the document. If the document
        already has a title, it is replaced. If it does not have a title, one
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
        are not part of the document content. The footer and header are
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

    def http_to_https(self) -> Self:
        """Convert all http links to https links.

        This method converts all http links in the HTML document to https
        links. https is now the standard for web communication.
        """
        for a in self.soup.find_all("a", href=True):
            if not "href" in a.attrs:
                continue

            href = str(a["href"])

            if href.startswith("http://"):
                a["href"] = "https://" + href[7:]

        self.remember("http_to_https")

        return self

    def remove_style_attributes(self) -> Self:
        """Remove all style attributes from the HTML document.

        This method removes all style attributes from the HTML document, which
        are not part of the document content. The style attributes are added by
        the OCR model.
        """
        for tag in self.soup.find_all(True):
            if "style" in tag.attrs:
                del tag.attrs["style"]

        self.remember("remove_style_attributes")

        return self

    def set_title_from_first_heading(self) -> Self:
        """Set the title of the HTML document from the first heading.

        This method sets the title of the HTML document to the text of the
        first heading (h1, h2, h3, h4, h5, or h6) found in the document. If no
        heading is found, the title is not changed.
        """
        first_heading = self.soup.find("h1")

        if first_heading and first_heading.get_text():
            self.set_title(first_heading.get_text())

        return self

    def correct(self) -> Self:
        """Apply all HTML corrections in the proper order."""
        return (self
            .group_nearby_text_divs()
            .remove_footers_and_headers()
            .remove_chandra_divs()
            .increase_heading_levels()
            .remove_unneeded_brs()
            .remove_unneeded_ps()
            .set_title_from_first_heading()
            .remove_style_attributes()
            .http_to_https()
        )
