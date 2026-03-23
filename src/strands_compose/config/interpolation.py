"""Docker Compose-style variable interpolation for YAML config values."""

from __future__ import annotations

import os
import re
from typing import Any

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


def interpolate(
    raw: dict[str, Any],
    *,
    variables: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Interpolate ${VAR} and ${VAR:-default} references in a YAML config dict.

    Lookup order: variables dict -> env dict -> default value -> raise error.

    Uses a two-pass strategy to resolve cross-variable references inside the
    ``vars:`` block before interpolating the rest of the config.  Pass 1
    resolves each var against env only; Pass 2 resolves each var sequentially
    against the pass-1 results so chains like ``B: "${A}y"`` work correctly.
    Any ``${VAR}`` pattern still present after two passes indicates a circular
    or undefined reference and raises ``ValueError``.

    Args:
        raw: Raw parsed YAML dict (will not be mutated — returns a new dict).
        variables: User-defined variables (from the ``vars:`` block in YAML).
            Values may be any type; non-string values are preserved when the
            entire string is a single ``${VAR}`` reference.
        env: Environment variables (defaults to ``os.environ`` if None).

    Returns:
        New dict with all string values interpolated.

    Raises:
        ValueError: If a variable is referenced but not found and has no
            default, or if a circular reference is detected in the vars block.
    """
    resolved_vars = dict(variables or {})
    resolved_env = env if env is not None else dict(os.environ)

    # Pass 1: resolve vars against env only (lenient — keeps ${VAR} if absent)
    resolved_vars = {k: _walk_lenient(v, {}, resolved_env) for k, v in resolved_vars.items()}

    # Pass 2: resolve vars sequentially so each resolved var is immediately
    # available to subsequent entries (handles chains like A -> B -> C).
    pass2: dict[str, Any] = {}
    for k, v in resolved_vars.items():
        pass2[k] = _walk_lenient(v, pass2, resolved_env)
    resolved_vars = pass2

    # Validate: remaining ${...} means circular or undefined reference.
    for val in resolved_vars.values():
        if isinstance(val, str):
            m = _VAR_PATTERN.search(val)
            if m:
                var_name = m.group(1).split(":-")[0]
                raise ValueError(
                    f"Unresolved variable reference '${{{var_name}}}' in vars block.\n"
                    f"Check for circular references or undefined variables."
                )

    return _walk(raw, resolved_vars, resolved_env)


def strip_anchors(raw: dict[str, Any]) -> dict[str, Any]:
    """Remove x-* keys (YAML anchor scratch pads) from the top level.

    Args:
        raw: Raw parsed YAML dict.

    Returns:
        New dict without top-level ``x-*`` keys.
    """
    return {k: v for k, v in raw.items() if not k.startswith("x-")}


def _walk(
    data: Any,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Recursively walk data and interpolate string values."""
    if isinstance(data, dict):
        return {k: _walk(v, variables, env) for k, v in data.items()}
    if isinstance(data, list):
        return [_walk(item, variables, env) for item in data]
    if isinstance(data, str) and "${" in data:
        return _interpolate_string(data, variables, env)
    return data


def _interpolate_string(
    value: str,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Interpolate all ${...} patterns in a single string value.

    If the entire string is a single ``${VAR}`` reference, the resolved value
    is returned in its original type (e.g. int stays int). Otherwise, all
    resolved values are cast to str and concatenated.
    """
    match = _VAR_PATTERN.fullmatch(value)
    if match is not None:
        return _resolve(match.group(1), variables, env)

    def _replacer(m: re.Match[str]) -> str:
        return str(_resolve(m.group(1), variables, env))

    return _VAR_PATTERN.sub(_replacer, value)


def _resolve(
    expr: str,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Resolve a single variable expression like ``VAR`` or ``VAR:-default``."""
    var_name, *rest = expr.split(":-", 1)
    default: str | None = rest[0] if rest else None

    if var_name in variables:
        return variables[var_name]

    if var_name in env:
        return env[var_name]

    if default is not None:
        return default

    raise ValueError(
        f"Variable '${{{var_name}}}' is not set in 'vars:' or environment, "
        f"and no default was provided.\n"
        f"Use ${{{var_name}:-fallback}} to set a fallback value."
    )


# ---------------------------------------------------------------------------
# Lenient variants — used only during the vars pre-resolution passes.
# They return the original ${expr} pattern unchanged instead of raising, so
# unresolved references survive to the post-pass validation step.
# ---------------------------------------------------------------------------


def _walk_lenient(
    data: Any,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Recursively walk data and interpolate strings; leaves ${VAR} unchanged if unresolved."""
    if isinstance(data, dict):
        return {k: _walk_lenient(v, variables, env) for k, v in data.items()}
    if isinstance(data, list):
        return [_walk_lenient(item, variables, env) for item in data]
    if isinstance(data, str) and "${" in data:
        return _interpolate_string_lenient(data, variables, env)
    return data


def _interpolate_string_lenient(
    value: str,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Interpolate ${...} patterns; returns ${expr} unchanged if variable not found."""
    match = _VAR_PATTERN.fullmatch(value)
    if match is not None:
        return _resolve_lenient(match.group(1), variables, env)

    def _replacer(m: re.Match[str]) -> str:
        return str(_resolve_lenient(m.group(1), variables, env))

    return _VAR_PATTERN.sub(_replacer, value)


def _resolve_lenient(
    expr: str,
    variables: dict[str, Any],
    env: dict[str, str],
) -> Any:
    """Resolve a single variable expression; returns ${expr} unchanged if not found."""
    var_name, *rest = expr.split(":-", 1)
    default: str | None = rest[0] if rest else None

    if var_name in variables:
        return variables[var_name]
    if var_name in env:
        return env[var_name]
    if default is not None:
        return default
    return f"${{{expr}}}"
