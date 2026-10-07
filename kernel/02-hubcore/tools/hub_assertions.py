"""Strict named assertions over one already-parsed JSON observation.

This module performs no I/O and does not establish observation provenance.
The caller must parse stdout strictly, bind it to the actual execution, and
treat ValueError as a rejected observation/configuration, never a passing run.
"""

from __future__ import annotations

import math
from typing import Any

__all__ = ["validate_assertions", "evaluate_assertions"]

_OPS = frozenset({"eq", "ne", "exists", "type", "eq_path", "ne_path"})
_TYPE_NAMES = frozenset({"null", "boolean", "integer", "number", "string", "array", "object"})
_BASE_FIELDS = frozenset({"id", "path", "op"})
_MISSING = object()


def _validate_json(value: Any, source: str) -> None:
    """Reject non-JSON types, nonfinite numbers and cycles without recursion."""
    pending = [(False, value)]
    active: set[int] = set()
    complete: set[int] = set()
    while pending:
        exiting, current = pending.pop()
        if exiting:
            active.remove(id(current))
            complete.add(id(current))
            continue
        kind = type(current)
        if current is None or kind in (str, bool, int):
            continue
        if kind is float:
            if not math.isfinite(current):
                raise ValueError(source + " contains a nonfinite number")
            continue
        if kind not in (list, dict):
            raise ValueError(source + " contains a non-JSON type")
        identity = id(current)
        if identity in active:
            raise ValueError(source + " contains a cycle")
        if identity in complete:
            continue
        if kind is dict and any(type(key) is not str for key in current):
            raise ValueError(source + " contains a non-string object key")
        active.add(identity)
        pending.append((True, current))
        values = current if kind is list else current.values()
        pending.extend((False, child) for child in values)


def _pointer_tokens(pointer: Any) -> list[str]:
    """Parse the JSON string form of RFC 6901; URI fragments are not accepted."""
    if type(pointer) is not str or (pointer and not pointer.startswith("/")):
        raise ValueError("assertion contains an invalid JSON pointer")
    if not pointer:
        return []
    tokens = pointer[1:].split("/")
    for token in tokens:
        index = 0
        while index < len(token):
            if token[index] == "~":
                if index + 1 == len(token) or token[index + 1] not in "01":
                    raise ValueError("assertion contains an invalid JSON pointer escape")
                index += 2
            else:
                index += 1
    # Decoding in this order ensures '~01' means literal '~1', not '/'.
    return [token.replace("~1", "/").replace("~0", "~") for token in tokens]


def validate_assertions(rules: Any) -> None:
    """Validate the entire rule set, raising a value-free ValueError if invalid.

    IDs are nonblank strings without surrounding whitespace and are unique.
    Every operation accepts exactly id/path/op, its required operand, and the
    optional nonblank scenario string. No candidate-provided pass field is used.
    """
    if type(rules) is not list or not rules:
        raise ValueError("assertions must be a nonempty JSON array")
    _validate_json(rules, "assertions")
    identifiers: set[str] = set()
    for assertion in rules:
        if type(assertion) is not dict:
            raise ValueError("each assertion must be a JSON object")
        operation = assertion.get("op")
        if type(operation) is not str or operation not in _OPS:
            raise ValueError("assertion has an unsupported operation")
        required = set(_BASE_FIELDS)
        if operation in ("eq", "ne", "type"):
            required.add("value")
        elif operation in ("eq_path", "ne_path"):
            required.add("other_path")
        fields = set(assertion)
        if fields not in (required, required | {"scenario"}):
            raise ValueError("assertion fields do not match its operation")
        identifier = assertion["id"]
        if type(identifier) is not str or not identifier or identifier.strip() != identifier:
            raise ValueError("assertion ID must be nonblank without surrounding whitespace")
        if identifier in identifiers:
            raise ValueError("assertion IDs must be unique")
        identifiers.add(identifier)
        _pointer_tokens(assertion["path"])
        if operation in ("eq_path", "ne_path"):
            _pointer_tokens(assertion["other_path"])
        if operation == "type":
            name = assertion["value"]
            if type(name) is not str or name not in _TYPE_NAMES:
                raise ValueError("assertion contains an unsupported type name")
        if "scenario" in assertion:
            scenario = assertion["scenario"]
            if type(scenario) is not str or not scenario.strip():
                raise ValueError("assertion scenario must be nonblank text")


def _resolve(actual: Any, pointer: str) -> Any:
    current = actual
    for token in _pointer_tokens(pointer):
        if type(current) is dict:
            if token not in current:
                return _MISSING
            current = current[token]
        elif type(current) is list:
            canonical = token == "0" or (
                bool(token) and "1" <= token[0] <= "9"
                and all("0" <= digit <= "9" for digit in token[1:])
            )
            if not canonical or not current:
                return _MISSING
            # Bound conversion first; enormous tokens must fail, not raise
            # Python's integer-string conversion limit or allocate huge ints.
            last_index = len(current) - 1
            if len(token) > len(str(last_index)):
                return _MISSING
            index = int(token)
            if index > last_index:
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current


def _strict_equal(left: Any, right: Any) -> bool:
    pending = [(left, right)]
    compared: set[tuple[int, int]] = set()
    while pending:
        first, second = pending.pop()
        kind = type(first)
        if kind is not type(second):
            return False
        if kind in (dict, list):
            pair = (id(first), id(second))
            if pair in compared:
                continue
            compared.add(pair)
            if len(first) != len(second):
                return False
            if kind is dict:
                if first.keys() != second.keys():
                    return False
                pending.extend((first[key], second[key]) for key in first)
            else:
                pending.extend(zip(first, second))
        elif first != second:
            return False
    return True


def _has_type(value: Any, name: str) -> bool:
    if name == "number":
        return type(value) in (int, float)
    expected = {
        "null": type(None), "boolean": bool, "integer": int,
        "string": str, "array": list, "object": dict,
    }
    return type(value) is expected[name]


def evaluate_assertions(actual: Any, rules: Any) -> list[dict[str, Any]]:
    """Calculate safe per-rule verdicts over actual; never trust pass lists.

    Both inputs must be JSON-compatible builtins without NaN/Infinity or cycles.
    Invalid input rejects the whole call via ValueError. Missing paths are false
    even for ne/ne_path. Comparison is recursively type-exact: 1, 1.0 and True
    are distinct; the type predicate 'number' accepts finite int or float.
    """
    validate_assertions(rules)
    _validate_json(actual, "actual")
    results: list[dict[str, Any]] = []
    for assertion in rules:
        operation = assertion["op"]
        observed = _resolve(actual, assertion["path"])
        passed, code = False, "path_missing"
        if observed is not _MISSING:
            if operation == "exists":
                passed, code = True, "passed"
            elif operation == "type":
                passed = _has_type(observed, assertion["value"])
                code = "passed" if passed else "type_mismatch"
            else:
                other = (_resolve(actual, assertion["other_path"])
                         if operation in ("eq_path", "ne_path") else assertion["value"])
                if other is _MISSING:
                    code = "other_path_missing"
                else:
                    equal = _strict_equal(observed, other)
                    wants_equal = operation in ("eq", "eq_path")
                    passed = equal if wants_equal else not equal
                    code = "passed" if passed else ("not_equal" if wants_equal else "equal")
        results.append({
            "id": assertion["id"], "passed": passed, "code": code,
            "path": assertion["path"], "op": operation,
        })
    return results
