"""One adapter for native parse failures at optional profile boundaries."""
from . import profile as p
from .syntax import ParseError, parse, parse_document


def native(source, *, one=False, max_nodes=100_000, max_depth=128):
    """Keep the native API unchanged; distinguish rejection from exhausted bounds."""
    try:
        parser = parse if one else parse_document
        return parser(source, max_nodes=max_nodes, max_depth=max_depth)
    except ParseError as error:
        # Native 1.0 has no typed resource error. Isolate its compatibility mapping.
        resource = str(error).startswith(("expression resource limit exceeded", "source exceeds"))
        kind = p.LimitError if resource else p.ProfileError
        raise kind(str(error)) from error


def failure(error):
    """The two optional CLIs use the same categories and completion semantics."""
    from .changes import ConflictError
    if isinstance(error, (p.LimitError, OSError, RecursionError)):
        category, code = "incomplete", 2
    elif isinstance(error, ConflictError):
        category, code = "conflict", 1
    elif isinstance(error, ValueError):
        category, code = "rejected", 1
    else:
        raise TypeError("not an expected boundary failure") from error
    return code, {"error": category, "complete": code == 1, "message": str(error)}
