"""Read independent unittest expectations without running the test's Python."""

from __future__ import annotations

import ast
import copy


def methods(source):
    tree = ast.parse(source)
    return {
        (cls.name, node.name): node
        for cls in tree.body
        if isinstance(cls, ast.ClassDef)
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


def assignments(nodes):
    result = {}
    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name):
            result[target.id] = value
    return result


class ExpandNames(ast.NodeTransformer):
    def __init__(self, assigned):
        self.assigned = assigned
        self.active = set()

    def visit_Name(self, node):
        if node.id not in self.assigned:
            return node
        if node.id in self.active:
            raise ValueError("cyclic expected value")
        self.active.add(node.id)
        result = self.visit(copy.deepcopy(self.assigned[node.id]))
        self.active.remove(node.id)
        return result


def expanded(node, assigned):
    return ExpandNames(assigned).visit(copy.deepcopy(node))


def literal(node):
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return literal(node.left) + literal(node.right)
    if isinstance(node, ast.Dict):
        return {
            literal(key): literal(value) for key, value in zip(node.keys, node.values, strict=True)
        }
    return ast.literal_eval(node)


def calls_parser(node, names):
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Name) and child.func.id in names:
            return True
        if isinstance(child.func, ast.Attribute) and child.func.attr == "parse_pairs":
            return True
    return False


def assertion_pairs(test):
    for node in ast.walk(test):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("assertEqual", "assertDictEqual")
            and len(node.args) >= 2
        ):
            yield node.args[:2]
        if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
            test_value = node.test
            if len(test_value.ops) == 1 and isinstance(test_value.ops[0], ast.Eq):
                yield [test_value.left, test_value.comparators[0]]


def parser_names(tree):
    names = {"parse_pairs"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "textparse":
            names.update(a.asname or a.name for a in node.names if a.name == "parse_pairs")
    return names


def independent_pair(pair, assigned, names):
    for actual, expected in (pair, pair[::-1]):
        try:
            if not calls_parser(expanded(actual, assigned), names):
                continue
            value = literal(expanded(expected, assigned))
        except (ValueError, TypeError, SyntaxError, RecursionError):
            continue
        if isinstance(value, dict) and any("=" in str(v) for v in value.values()):
            return True
    return False


def independent_assertion(test, tree):
    assigned = assignments(tree.body)
    assigned.update(assignments(ast.walk(test)))
    names = parser_names(tree)
    return any(independent_pair(pair, assigned, names) for pair in assertion_pairs(test))
