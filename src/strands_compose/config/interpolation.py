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

    # Passes 1 and 2 run non-strict: a var may legitimately reference another var
    # that is not resolved yet, so unresolved ${...} must survive to be retried.
    # Pass 1: resolve vars against env only.
    resolved_vars = {k: _walk(v, {}, resolved_env, strict=False) for k, v in resolved_vars.items()}

    # Pass 2: resolve vars sequentially so each resolved var is immediately
    # available to subsequent entries (handles chains like A -> B -> C).
    pass2: dict[str, Any] = {}
    for k, v in resolved_vars.items():
        pass2[k] = _walk(v, pass2, resolved_env, strict=False)
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

    # The config itself is strict: every reference must resolve here.
    return _walk(raw, resolved_vars, resolved_env, strict=True)


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
    *,
    strict: bool,
) -> Any:
    """Recursively walk data and interpolate string values.

    Args:
        data: Any parsed YAML value.
        variables: Resolved ``vars:`` values.
        env: Environment variables.
        strict: Raise on an unresolved reference; when ``False`` leave the
            original ``${expr}`` in place for the caller to validate later.

    Returns:
        The value with strings interpolated.
    """
    if isinstance(data, dict):
        return {k: _walk(v, variables, env, strict=strict) for k, v in data.items()}
    if isinstance(data, list):
        return [_walk(item, variables, env, strict=strict) for item in data]
    if isinstance(data, str) and "${" in data:
        return _interpolate_string(data, variables, env, strict=strict)
    return data


def _interpolate_string(
    value: str,
    variables: dict[str, Any],
    env: dict[str, str],
    *,
    strict: bool,
) -> Any:
    """Interpolate all ``${...}`` patterns in a single string value.

    A string that is exactly one ``${VAR}`` keeps the value's original type
    (an int stays an int); a mixed string concatenates everything as text.

    Args:
        value: The string to interpolate.
        variables: Resolved ``vars:`` values.
        env: Environment variables.
        strict: Raise on an unresolved reference instead of leaving it in place.

    Returns:
        The interpolated value, typed when the whole string was one reference.
    """
    match = _VAR_PATTERN.fullmatch(value)
    if match is not None:
        return _resolve(match.group(1), variables, env, strict=strict)

    def _replacer(m: re.Match[str]) -> str:
        return str(_resolve(m.group(1), variables, env, strict=strict))

    return _VAR_PATTERN.sub(_replacer, value)


def _resolve(
    expr: str,
    variables: dict[str, Any],
    env: dict[str, str],
    *,
    strict: bool,
) -> Any:
    """Resolve one expression like ``VAR`` or ``VAR:-default``.

    Args:
        expr: The text inside ``${...}``.
        variables: Resolved ``vars:`` values.
        env: Environment variables.
        strict: Raise when unresolved; when ``False`` return the original
            ``${expr}`` so the vars pre-passes can run again over it.

    Returns:
        The resolved value, or ``${expr}`` unchanged when not strict.

    Raises:
        ValueError: Strict mode and the variable has no value and no default.
    """
    var_name, *rest = expr.split(":-", 1)
    default: str | None = rest[0] if rest else None

    if var_name in variables:
        return variables[var_name]

    if var_name in env:
        return env[var_name]

    if default is not None:
        return default

    if not strict:
        return f"${{{expr}}}"

    raise ValueError(
        f"Variable '${{{var_name}}}' is not set in 'vars:' or environment, "
        f"and no default was provided.\n"
        f"Use ${{{var_name}:-fallback}} to set a fallback value."
    )
