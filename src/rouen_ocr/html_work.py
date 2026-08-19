"""Base class."""

from bs4 import BeautifulSoup


class MissingStepError(ValueError):
    """Raised when a required step has not been done."""
    pass


class HtmlWork:
    """Base class for HTML work."""

    def __init__(self, html: str | object) -> None:
        self.steps = []
        if isinstance(html, HtmlWork):
            self.soup = html.soup
        elif isinstance(html, str):
            self.parse(html)
        else:
            raise TypeError(f"Invalid type for html: {type(html)}")

    def parse(self, html: str) -> None:
        """Parse the HTML document or fragment."""
        self.soup = BeautifulSoup(html, "html.parser")

    def remember(self, step: str) -> None:
        """Remember a step has been done.

        This keeps tracks of the steps that have been applied to the HTML and
        their order, so that dependent steps can be verified.

        Input:
            step: The name of the step that has been done.
        """
        self.steps.append(step)

    def must_not_have(self, steps: str | list[str]) -> None:
        """Ensure a step has not been done.

        Some steps may depend on specific previous steps. This method checks
        that the specified steps have not been done, and raises an exception if
        they have.

        Input:
            steps: A step name or a list of step names that must not have been
            done.
        """
        if isinstance(steps, list):
            for step in steps:
                self.must_not_have(step)
        elif steps in self.steps:
            raise ValueError(f"Step {steps} has already been done.")

    def require_step(self, steps: str | list[str]) -> None:
        """Ensure a required step has been done.

        Some steps may depend on specific previous steps. This method checks
        that the required steps have been done, and raises an exception if not.

        Input:
            steps: A step name or a list of step names that must have been done.

        Raises:
            MissingStepError: If any of the required steps have not been done.
        """

        if isinstance(steps, list):
            for step in steps:
                self.require_step(step)
        elif steps not in self.steps:
            raise MissingStepError(f"Step {steps} has not been done.")

    def __str__(self) -> str:
        """Return the corrected HTML document or fragment."""
        return str(self.soup)
