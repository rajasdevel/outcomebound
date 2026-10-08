"""A deliberately small JSON Schema subset, standard library only.

The engine validates what it reads against the shipped schemas through this
module, so a schema cannot disagree with the code it describes without a check
noticing. This covers the keywords the shipped schemas actually use; anything
else is ignored rather than silently approximated, and every message is
``<path> <problem>`` so a caller can surface it verbatim.

Ignoring a keyword silently un-validates the field it guards, so the subset is
pinned by ``tests/test_schemacheck.py``: every keyword ``schemas/*.json``
actually uses must appear in :data:`SUPPORTED`.
"""

from __future__ import annotations

import re
from typing import Any

TYPE_CHECKS = {
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
    "string": lambda value: isinstance(value, str),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
}

SUPPORTED = frozenset(
    {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minItems",
        "minLength",
        "pattern",
        "uniqueItems",
    }
)


def _equal(instance: Any, expected: Any) -> bool:
    """Compare with the same bool discipline ``type`` applies.

    ``True == 1`` in Python, so a plain ``==`` would let ``true`` satisfy
    ``{"const": 1}`` while ``{"type": "integer"}`` rejects it. JSON tells the two
    apart, so the subset does too.
    """

    if isinstance(instance, bool) != isinstance(expected, bool):
        return False
    return instance == expected


def _type_error(instance: Any, schema: dict[str, Any], path: str) -> str | None:
    """A type mismatch stops this branch before its other constraints run."""

    expected = schema.get("type")
    if isinstance(expected, str):
        check = TYPE_CHECKS.get(expected)
        if check is not None and not check(instance):
            return f"{path} must be of type {expected}"
    elif isinstance(expected, list):
        checks = [TYPE_CHECKS[name] for name in expected if name in TYPE_CHECKS]
        if checks and not any(check(instance) for check in checks):
            return f"{path} must be of type {' or '.join(expected)}"
    return None


def _string_errors(instance: str, schema: dict[str, Any], path: str) -> list[str]:
    errors = []
    minimum = schema.get("minLength")
    if isinstance(minimum, int) and not isinstance(minimum, bool) and len(instance) < minimum:
        errors.append(f"{path} must be at least {minimum} character(s)")
    if "pattern" in schema and not re.search(schema["pattern"], instance):
        errors.append(f"{path} does not match pattern {schema['pattern']!r}")
    return errors


def _object_errors(instance: dict[str, Any], schema: dict[str, Any], path: str) -> list[str]:
    errors = [
        f"{path} is missing required field {key!r}"
        for key in schema.get("required", [])
        if key not in instance
    ]
    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        extra = sorted(set(instance) - set(properties))
        if extra:
            errors.append(f"{path} has unknown field(s): {', '.join(extra)}")
    for key, subschema in properties.items():
        if key in instance:
            errors.extend(validate(instance[key], subschema, f"{path}.{key}"))
    return errors


def _array_errors(instance: list[Any], schema: dict[str, Any], path: str) -> list[str]:
    errors = []
    minimum = schema.get("minItems")
    if isinstance(minimum, int) and not isinstance(minimum, bool) and len(instance) < minimum:
        errors.append(f"{path} must have at least {minimum} item(s)")
    unique = schema.get("uniqueItems")
    if unique is not None and not isinstance(unique, bool):
        # A malformed constraint is a schema defect, and ignoring it would
        # un-validate the field it was written to guard -- which is the one
        # failure mode this whole subset exists to prevent. Fail closed.
        errors.append(f"{path} has a malformed uniqueItems constraint")
    elif unique is True:
        # JSON array members need not be hashable. `_equal` keeps 1 and true distinct
        # here as it does for const and enum.
        seen: list[Any] = []
        for item in instance:
            if any(_equal(item, other) for other in seen):
                errors.append(f"{path} must not repeat items")
                break
            seen.append(item)
    items = schema.get("items")
    if isinstance(items, dict):
        for index, item in enumerate(instance):
            errors.extend(validate(item, items, f"{path}[{index}]"))
    return errors


def validate(instance: Any, schema: Any, path: str = "$") -> list[str]:
    """Return every defect found, deepest-first per branch; empty means valid."""

    if not isinstance(schema, dict):
        return []
    problem = _type_error(instance, schema, path)
    if problem is not None:
        return [problem]

    errors = []
    if "const" in schema and not _equal(instance, schema["const"]):
        errors.append(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and not any(_equal(instance, item) for item in schema["enum"]):
        allowed = ", ".join(str(item) for item in schema["enum"])
        errors.append(f"{path} must be one of: {allowed}")
    if isinstance(instance, str):
        errors.extend(_string_errors(instance, schema, path))
    if isinstance(instance, dict):
        errors.extend(_object_errors(instance, schema, path))
    if isinstance(instance, list):
        errors.extend(_array_errors(instance, schema, path))
    return errors
