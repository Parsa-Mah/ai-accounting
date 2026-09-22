"""Domain exceptions. Mapped to HTTP responses by handlers in app.main."""


class NotFoundError(Exception):
    """Requested entity does not exist (HTTP 404)."""


class ConflictError(Exception):
    """Write conflicts with existing data or domain rules (HTTP 409)."""


class ValidationError(Exception):
    """Submitted content is well-formed but violates a domain rule (HTTP 422)."""
