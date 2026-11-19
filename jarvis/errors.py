"""Errors Jarvis raises on purpose. The web layer maps them to HTTP codes."""


class JarvisError(Exception):
    """Base class for all expected errors."""


class InvalidInputError(JarvisError):
    """The caller sent something we cannot use."""


class LLMError(JarvisError):
    """The model answered with an error."""


class LLMUnavailableError(LLMError):
    """The model server cannot be reached at all."""
