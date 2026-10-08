"""The schema subset actually validates the artifacts this repository ships."""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools.schemacheck import SUPPORTED, validate

ROOT = Path(__file__).resolve().parent.parent

# JSON Schema keywords that carry no constraint, so ignoring them is correct.
ANNOTATIONS = frozenset({"$schema", "$id", "title", "description"})


def _schema(name):
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


# One row per defect: (keyword under test, instance, schema, expected message fragment).
# test_every_supported_keyword_is_exercised pins this table against SUPPORTED, so a keyword
# added to the subset without a case here — or without an implementation — goes red.
KEYWORD_CASES: tuple[tuple[str, Any, dict[str, Any], str], ...] = (
    ("required", {"a": 1}, {"type": "object", "required": ["b"]}, "missing required field 'b'"),
    (
        "additionalProperties",
        {"a": 1},
        {"type": "object", "additionalProperties": False, "properties": {}},
        "has unknown field(s): a",
    ),
    ("type", "x", {"type": "integer"}, "must be of type integer"),
    ("type", True, {"type": "integer"}, "must be of type integer"),
    ("enum", 3, {"enum": [1, 2]}, "must be one of: 1, 2"),
    ("enum", True, {"enum": [1, 2]}, "must be one of: 1, 2"),
    ("const", 3, {"const": 1}, "must equal 1"),
    ("const", True, {"const": 1}, "must equal 1"),
    ("const", 1, {"const": True}, "must equal True"),
    ("minItems", [], {"type": "array", "minItems": 1}, "must have at least 1 item(s)"),
    ("minLength", "", {"type": "string", "minLength": 1}, "must be at least 1 character(s)"),
    ("pattern", "zz", {"type": "string", "pattern": "^[0-9a-f]+$"}, "does not match pattern"),
    ("items", [1], {"type": "array", "items": {"type": "string"}}, "$[0] must be of type string"),
    ("uniqueItems", ["a", "a"], {"type": "array", "uniqueItems": True}, "must not repeat items"),
    (
        "properties",
        {"k": [1]},
        {"type": "object", "properties": {"k": {"type": "array", "items": {"type": "string"}}}},
        "$.k[0] must be of type string",
    ),
)


@pytest.mark.parametrize(
    "instance, schema, expected_fragment",
    [case[1:] for case in KEYWORD_CASES],
    ids=[f"{case[0]}-{index}" for index, case in enumerate(KEYWORD_CASES)],
)
def test_each_supported_keyword_reports_its_own_defect(instance, schema, expected_fragment):
    errors = validate(instance, schema)
    assert any(expected_fragment in error for error in errors), errors


def test_every_supported_keyword_is_exercised():
    """An unexercised keyword is a claim of support with nothing behind it."""
    exercised = {case[0] for case in KEYWORD_CASES}
    assert exercised == set(SUPPORTED), (
        f"unexercised: {sorted(set(SUPPORTED) - exercised)}; "
        f"not in SUPPORTED: {sorted(exercised - set(SUPPORTED))}"
    )


def test_const_and_enum_apply_the_same_bool_discipline_as_type():
    """True == 1 in Python but not in JSON, so a bool must not satisfy an int member.

    The refusals, each with its message, are KEYWORD_CASES rows; these are the matches.
    """
    assert validate(True, {"const": True}) == []
    assert validate(1, {"const": 1}) == []


def test_valid_instances_report_nothing():
    assert (
        validate({"version": 1}, {"type": "object", "properties": {"version": {"const": 1}}}) == []
    )


@pytest.mark.parametrize("schema", [None, False, 1, [], "schema"])
def test_non_object_schemas_keep_the_existing_empty_result(schema):
    assert validate("value", schema) == []


@pytest.mark.parametrize(
    "expected_type, message",
    [
        ("string", "$ must be of type string"),
        (["string", "array"], "$ must be of type string or array"),
    ],
)
def test_type_mismatch_stops_before_other_constraints(expected_type, message):
    assert validate(1, {"type": expected_type, "const": 2, "enum": [3]}) == [message]


def test_multiple_schema_defects_keep_their_report_order():
    schema = {
        "type": "object",
        "const": {},
        "enum": [{}],
        "required": ["missing"],
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1, "pattern": "^x$"},
            "tags": {
                "type": "array",
                "minItems": 3,
                "uniqueItems": True,
                "items": {"type": "string"},
            },
        },
    }
    assert validate({"title": "", "tags": [1, 1], "extra": True}, schema) == [
        "$ must equal {}",
        "$ must be one of: {}",
        "$ is missing required field 'missing'",
        "$ has unknown field(s): extra",
        "$.title must be at least 1 character(s)",
        "$.title does not match pattern '^x$'",
        "$.tags must have at least 3 item(s)",
        "$.tags must not repeat items",
        "$.tags[0] must be of type string",
        "$.tags[1] must be of type string",
    ]


def _shipped_schema_names():
    """Every schema this checkout ships, discovered rather than listed.

    A list written by hand would silently exempt every schema left off it, so a
    schema added later could use a keyword the subset does not implement and
    nothing would say so. Discovery covers each new schema by default.
    """

    return sorted(path.name for path in (ROOT / "schemas").glob("*.schema.json"))


def test_every_keyword_the_shipped_schemas_use_is_enforced_not_ignored():
    """A keyword outside the subset silently un-validates the field it guards."""
    names = _shipped_schema_names()
    assert names, "no shipped schemas were discovered"
    for name in names:
        text = (ROOT / "schemas" / name).read_text(encoding="utf-8")
        used = set(re.findall(r'"(\$?[A-Za-z_]+)":', text))
        unenforced = sorted(used - SUPPORTED - ANNOTATIONS - _property_names(_schema(name)))
        assert not unenforced, f"{name} uses unenforced keyword(s): {unenforced}"


def test_shipped_schemas_are_all_readable_in_the_supported_subset():
    """Discovery is only useful if every discovered schema actually parses and
    validates its own shape; an unreadable one would otherwise be skipped."""
    for name in _shipped_schema_names():
        schema = _schema(name)
        assert isinstance(schema, dict) and schema, name


def _property_names(node):
    """Object keys the schema declares are data, not keywords."""
    names = set()
    if isinstance(node, dict):
        names.update(node.get("properties", {}))
        for value in node.values():
            names |= _property_names(value)
    elif isinstance(node, list):
        for value in node:
            names |= _property_names(value)
    return names


def test_shipped_validation_plan_example_validates():
    example = json.loads(
        (ROOT / "templates/validation/plan.example.json").read_text(encoding="utf-8")
    )
    assert validate(example, _schema("validation-plan.schema.json")) == []


def test_unique_items_refuses_repeats_and_fails_closed_on_a_malformed_constraint():
    """Sorted-unique arrays are enforced, not merely described.

    `uniqueItems` is the keyword the discovery document's `harness_markers`
    declares, so a hand-written document that repeats a marker is refused rather
    than quietly admitted. A non-boolean constraint is a schema defect: silently
    ignoring it would un-validate the very field it was written to guard.
    """

    # A repeat's refusal, with its message, is a KEYWORD_CASES row.
    assert validate(["a", "b"], {"type": "array", "uniqueItems": True}) == []
    assert validate([], {"type": "array", "uniqueItems": True}) == []
    # JSON tells 1 and true apart, and so does this subset.
    assert validate([1, True], {"type": "array", "uniqueItems": True}) == []
    assert validate([{"a": 1}, {"a": 1}], {"type": "array", "uniqueItems": True}) != []
    # `false` declares no constraint, which is JSON Schema's own meaning.
    assert validate(["a", "a"], {"type": "array", "uniqueItems": False}) == []
    malformed = validate(["a"], {"type": "array", "uniqueItems": "yes"})
    assert any("malformed uniqueItems" in error for error in malformed), malformed


def test_the_discovery_schema_declares_its_sorted_unique_marker_array():
    """`harness_markers` is uniqueItems with the five names."""

    schema = _schema("discovery.schema.json")
    markers = schema["properties"]["observations"]["properties"]["observed"]["properties"][
        "harness_markers"
    ]
    assert markers["uniqueItems"] is True
    assert markers["items"]["enum"] == [
        ".agents/skills/",
        ".claude/",
        ".codex/",
        ".cursor/",
        ".gemini/",
    ]
