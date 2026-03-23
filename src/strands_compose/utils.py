"""Shared low-level utilities for the strands_compose package."""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .exceptions import ImportResolutionError

if TYPE_CHECKING:
    from types import ModuleType


def import_from_path(import_path: str) -> Any:
    """Import a Python object from a ``module.path:ObjectName`` string.

    Args:
        import_path: Import string in ``"module.path:ObjectName"`` format.

    Returns:
        The imported object.

    Raises:
        ValueError: If format is invalid (missing ``:``)."
        ImportError: If module cannot be imported.
        AttributeError: If object does not exist in module.
    """
    if ":" not in import_path:
        raise ValueError(
            f"Import path must be in 'module.path:ObjectName' format, got: {import_path!r}"
        )
    module_path, obj_name = import_path.rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, obj_name)


def load_object(spec: str, *, target: str = "object") -> Any:
    """Load a Python object from a module-path or file-path spec.

    This is the **unified entry point** for resolving any
    ``module.path:ObjectName`` or ``./file.py:ObjectName`` import spec
    used throughout the config layer (agent factories, MCP server
    factories, model classes, session manager classes, hook classes,
    graph-edge conditions, etc.).

    The ``target`` kwarg is used **only** in error messages so that
    failures clearly identify what was being loaded.

    Args:
        spec: Import spec — either ``"module.path:ObjectName"`` or a
            filesystem path (containing ``/`` or ``\\``) with a colon-
            separated attribute, e.g. ``"/abs/path/file.py:create"``.
        target: Human-readable label for error messages, e.g.
            ``"agent factory"``, ``"MCP server"``, ``"graph condition"``.

    Returns:
        The imported Python object.

    Raises:
        ImportResolutionError: If the spec is malformed, the module/file
            cannot be loaded, or the attribute does not exist.
    """
    if ":" not in spec:
        raise ImportResolutionError(
            f"{target.capitalize()} import spec must be in 'module.path:Name' "
            f"or './file.py:Name' format, got: {spec!r}"
        )

    path_part, obj_name = spec.rsplit(":", 1)
    is_file_path = "/" in path_part or "\\" in path_part

    try:
        if is_file_path:
            module = load_module_from_file(path_part)
            if not hasattr(module, obj_name):
                raise ImportResolutionError(
                    f"{target.capitalize()} file '{path_part}' has no attribute '{obj_name}'"
                )
            return getattr(module, obj_name)

        return import_from_path(spec)
    except ImportResolutionError:
        raise
    except (ImportError, FileNotFoundError, AttributeError) as exc:
        raise ImportResolutionError(f"Failed to load {target} from '{spec}': {exc}") from exc


def load_module_from_file(path: str | Path) -> ModuleType:
    """Load a Python file as a module.

    Uses a deterministic module name based on the file's absolute path
    so repeated loads of the same file reuse the same name.

    Args:
        path: Path to a ``.py`` file.

    Returns:
        The loaded module.

    Raises:
        FileNotFoundError: If the file does not exist.
        ImportError: If the file cannot be loaded.
    """
    file_path = Path(path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    path_hash = hashlib.md5(str(file_path).encode(), usedforsecurity=False).hexdigest()[:12]
    module_name = f"_strands_compose_{file_path.stem}_{path_hash}"

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for: {file_path}")

    if module_name in sys.modules:
        del sys.modules[module_name]

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise ImportError(f"Failed to load file {file_path}: {exc}") from exc

    # Remove from sys.modules to avoid polluting the global module namespace.
    # The returned module object remains usable —
    # only the sys.modules entry is dropped.
    # This means subsequent ``import <module_name>`` statements won't resolve,
    # It's intentional: these are user-provided files, not library modules.
    # For hot-reload, the ``del`` above ensures a fresh exec on every call.
    sys.modules.pop(module_name, None)
    return module


# ── CLI error formatting ──────────────────────────────────────────────────────


class _SuppressTaskExceptions(logging.Filter):
    """Suppress asyncio 'Task exception was never retrieved' log entries.

    These originate from strands' internal event loop when exceptions
    escape sub-tasks. They are already surfaced via the ERROR StreamEvent
    emitted by EventPublisher, so the raw asyncio traceback is redundant.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        return "exception was never retrieved" not in record.getMessage()


def _format_exception(exc: BaseException) -> str:
    """Format an exception as ``module.ClassName: message`` (multi-line).

    For exceptions whose ``__module__`` is ``builtins`` the module prefix is
    omitted so that ``ValueError: …`` is shown instead of ``builtins.ValueError: …``.
    """
    cls = type(exc)
    module = getattr(cls, "__module__", None) or ""
    qualname = cls.__qualname__
    prefix = f"{module}.{qualname}" if module and module != "builtins" else qualname
    return f"{prefix}:\n{exc}" if str(exc) else prefix


@contextlib.contextmanager
def cli_errors(*, exit_code: int = 1) -> Iterator[None]:
    """Catch unhandled exceptions and print a clean, user-friendly message.

    .. warning::

        **CLI-only** — this context manager calls ``sys.exit()`` on errors,
        which raises ``SystemExit``.  Do **not** use it in ASGI/WSGI server
        code (FastAPI, Flask, etc.) where ``SystemExit`` would kill the
        worker process.  For server code, catch exceptions directly.

    Intended for CLI entry points — wraps the body so that configuration
    errors, auth failures, network problems, etc. are displayed without a
    full Python traceback::

        with cli_errors():
            asyncio.run(main())

    ``KeyboardInterrupt`` and ``SystemExit`` are **not** caught.

    Args:
        exit_code: Process exit code used after printing the error.
                   Set to ``0`` to suppress ``sys.exit`` (useful in tests).
    """
    _asyncio = logging.getLogger("asyncio")
    _filter = _SuppressTaskExceptions()
    _asyncio.addFilter(_filter)
    try:
        yield
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        msg = f"\n{_format_exception(exc)}\n"
        if sys.stderr.isatty():
            msg = f"\033[31m{msg}\033[0m"
        print(msg, file=sys.stderr)  # noqa: T201
        if exit_code:
            sys.exit(exit_code)
    finally:
        _asyncio.removeFilter(_filter)
