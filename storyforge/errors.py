class TemplateError(ValueError):
    """Raised when a template is malformed or references undeclared tokens."""


class ResolutionError(ValueError):
    """Raised when required variables are missing during resolution."""
