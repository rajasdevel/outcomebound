"""Literal effects of inline programs; input is inspected, never executed."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class FilePath(str):
    """A literal Path value, distinct from file content and ordinary strings."""


class FileHandle:
    """An open handle whose path and mode have already been recorded."""


class Data:
    """File content or library data whose value is not evaluated by the reader."""


PROCESS_MODULES = {"subprocess", "os", "asyncio", "pty", "multiprocessing", "concurrent"}
PROCESS_CALLS = {
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "subprocess.Popen",
}
PURE_CALLS = {
    "print",
    "str",
    "int",
    "float",
    "bool",
    "len",
    "list",
    "tuple",
    "dict",
    "set",
    "frozenset",
    "sorted",
    "reversed",
    "enumerate",
    "zip",
    "range",
    "min",
    "max",
    "sum",
    "all",
    "any",
    "isinstance",
    "type",
    "repr",
    "input",
    "json.loads",
    "json.dumps",
    "hashlib.sha256",
}
DATA_METHODS = {
    "replace",
    "strip",
    "lstrip",
    "rstrip",
    "split",
    "splitlines",
    "join",
    "index",
    "find",
    "startswith",
    "endswith",
    "encode",
    "decode",
    "format",
    "items",
    "keys",
    "values",
    "get",
    "copy",
    "append",
    "extend",
    "update",
    "pop",
    "hexdigest",
}


class PythonEffects(ast.NodeVisitor):
    def __init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.aliases: dict[str, str] = {}
        self.reads: list[str] = []
        self.writes: list[str] = []
        self.runs: list[list[str]] | None = []
        self.dynamic = False
        self.invalidated: list[Any] = []

    def uncertain(self) -> None:
        self.dynamic = True
        self.runs = None

    def name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return self.name(node.value) + "." + node.attr
        return ""

    def value(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            value = self.values.get(node.id)
            return None if self.tainted(value) else value
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return [self.value(item) for item in node.elts]
        if isinstance(node, ast.Subscript):
            return self.subscript(node)
        if isinstance(node, ast.Dict):
            return self.mapping(node)
        if isinstance(node, ast.BinOp):
            return self.binary(node)
        if isinstance(node, ast.Attribute) and node.attr == "parent":
            base = self.value(node.value)
            if isinstance(base, FilePath):
                return FilePath(Path(base).parent)
        if isinstance(node, ast.Call):
            return self.call_value(node)
        return None

    def subscript(self, node: ast.Subscript) -> Any:
        base = self.value(node.value)
        if isinstance(base, Data):
            return Data()
        key = self.value(node.slice)
        if isinstance(base, dict) and isinstance(key, str):
            return base.get(key)
        return None

    def mapping(self, node: ast.Dict) -> Any:
        keys = [self.value(key) for key in node.keys if key is not None]
        if len(keys) == len(node.keys) and all(isinstance(k, str) for k in keys):
            return dict(zip(keys, (self.value(v) for v in node.values), strict=True))
        return None

    def binary(self, node: ast.BinOp) -> Any:
        left, right = self.value(node.left), self.value(node.right)
        if isinstance(left, str) and isinstance(right, str):
            if isinstance(node.op, ast.Div) and isinstance(left, FilePath):
                return FilePath(Path(left) / right)
            if isinstance(node.op, ast.Add):
                return left + right
        if (
            isinstance(node.op, ast.Add)
            and isinstance(left, (str, Data))
            and isinstance(right, (str, Data))
        ):
            return Data()
        return None

    def call_value(self, node: ast.Call) -> Any:
        name = self.name(node.func)
        parts = [self.value(arg) for arg in node.args]
        if (
            name in ("Path", "pathlib.Path")
            and not node.keywords
            and parts
            and all(isinstance(part, str) for part in parts)
        ):
            return FilePath(Path(*parts))
        if name == "str" and len(parts) == 1 and isinstance(parts[0], str):
            return str(parts[0])
        if name in ("open", "io.open", "builtins.open"):
            return FileHandle()
        if name in PURE_CALLS or name in PROCESS_CALLS:
            return Data()
        if isinstance(node.func, ast.Attribute):
            return self.method_value(self.value(node.func.value), node.func.attr, parts)
        return None

    def method_value(self, base: Any, method: str, parts: list[Any]) -> Any:
        if isinstance(base, FilePath):
            if method == "joinpath" and all(isinstance(p, str) for p in parts):
                return FilePath(Path(base, *parts))
            if method in ("read_text", "read_bytes"):
                return Data()
            if method == "open":
                return FileHandle()
        if method == "items" and isinstance(base, dict):
            return list(base.items())
        if isinstance(base, (str, bytes, list, tuple, dict, Data)) and method in DATA_METHODS:
            return Data()
        if isinstance(base, FileHandle) and method in ("read", "readlines", "write", "close"):
            return Data()
        return None

    def bind(self, target: ast.AST, value: Any) -> None:
        if isinstance(target, ast.Name):
            self.values[target.id] = value
            self.aliases.pop(target.id, None)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for i, item in enumerate(target.elts):
                self.bind(
                    item, value[i] if isinstance(value, (list, tuple)) and i < len(value) else None
                )
        elif isinstance(target, ast.Subscript):
            self.mutate(target.value)
        else:
            self.uncertain()

    def tainted(self, value: Any) -> bool:
        if any(value is old for old in self.invalidated):
            return True
        if isinstance(value, dict):
            return any(self.tainted(item) for item in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(self.tainted(item) for item in value)
        return False

    def mutate(self, receiver: ast.AST) -> None:
        base = self.value(receiver)
        if isinstance(base, (list, tuple, dict, set)):
            # Keep the object invalid across aliases, nested containers and branch restores.
            self.invalidated.append(base)
            self.uncertain()
        elif not isinstance(base, Data):
            self.uncertain()

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            self.aliases[item.asname or item.name] = item.name
            if item.asname and item.name.split(".")[0] in PROCESS_MODULES:
                self.runs = None

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            self.aliases[item.asname or item.name] = (node.module or "") + "." + item.name
            if (node.module or "").split(".")[0] in PROCESS_MODULES or item.name == "*":
                self.uncertain()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(self.values.get(node.id), (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.uncertain()
        if self.name(node).split(".")[0] in PROCESS_MODULES or self.name(node) == "importlib":
            self.uncertain()
        if (
            isinstance(node.ctx, ast.Load)
            and node.id not in self.values
            and self.name(node) not in PURE_CALLS
            and node.id
            not in ("PermissionError", "ValueError", "TypeError", "OSError", "Exception")
        ):
            self.uncertain()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if self.name(node).split(".")[0] in PROCESS_MODULES:
            self.uncertain()
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        value = self.value(node.value)
        for target in node.targets:
            self.bind(target, value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self.bind(node.target, self.value(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
            self.bind(node.target, self.value(node.value))

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.visit(node.value)
        self.mutate(node.target.value if isinstance(node.target, ast.Subscript) else node.target)
        self.bind(node.target, None)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self.bind(target, None)

    def visit_For(self, node: ast.For) -> None:
        starts = len(self.runs) if self.runs is not None else 0
        self.visit(node.iter)
        values = self.value(node.iter)
        for value in values if isinstance(values, (list, tuple, dict)) else [None]:
            self.bind(node.target, value)
            for statement in node.body:
                self.visit(statement)
        for statement in node.orelse:
            self.visit(statement)
        if self.runs is not None and len(self.runs) != starts:
            self.runs = None

    def comprehension(self, node: Any, index: int = 0) -> None:
        if index == len(node.generators):
            for value in (node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,):
                self.visit(value)
            return
        generator = node.generators[index]
        self.visit(generator.iter)
        values = self.value(generator.iter)
        saved = self.values.copy()
        for value in values if isinstance(values, (list, tuple, dict)) else [values]:
            self.bind(generator.target, value)
            for condition in generator.ifs:
                self.visit(condition)
            self.comprehension(node, index + 1)
        self.values = saved

    def visit_DictComp(
        self, node: ast.DictComp | ast.ListComp | ast.SetComp | ast.GeneratorExp
    ) -> None:
        self.comprehension(node)

    visit_ListComp = visit_DictComp
    visit_SetComp = visit_DictComp
    visit_GeneratorExp = visit_DictComp

    def visit_If(self, node: ast.AST) -> None:
        saved = self.values.copy()
        starts = len(self.runs) if self.runs is not None else 0
        self.generic_visit(node)
        if self.runs is not None and len(self.runs) != starts:
            self.runs = None
        # Neither branch supplies a literal binding for subsequent effects.
        assigned = {
            n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        }
        self.values = {k: v for k, v in saved.items() if k not in assigned}

    visit_Try = visit_If
    visit_While = visit_If
    visit_Match = visit_If

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.values[node.name] = node
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)
        for decorator in node.decorator_list:
            self.visit(decorator)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in (*node.args.defaults, *node.args.kw_defaults):
            if default is not None:
                self.visit(default)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.uncertain()
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.values[node.name] = Data()
        for statement in node.body:
            self.visit(statement)

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars:
                self.bind(item.optional_vars, self.value(item.context_expr))
        for statement in node.body:
            self.visit(statement)

    def path(self, node: ast.AST | None, *, write: bool = False) -> None:
        value = self.value(node) if node is not None else None
        if isinstance(value, str) and value and "\0" not in value:
            (self.writes if write else self.reads).append(str(value))
        else:
            self.dynamic = True

    def operand(self, node: ast.Call, position: int, keyword: str) -> ast.AST | None:
        return (
            node.args[position]
            if len(node.args) > position
            else next((k.value for k in node.keywords if k.arg == keyword), None)
        )

    def process(self, node: ast.Call) -> None:
        operand = self.operand(node, 0, "args")
        argv = self.value(operand) if operand is not None else None
        shell = next((self.value(k.value) for k in node.keywords if k.arg == "shell"), False)
        if isinstance(argv, str):
            argv = [argv]  # Without shell=True a string names one executable, not shell words.
        if (
            isinstance(argv, list)
            and argv
            and all(isinstance(x, str) for x in argv)
            and shell is False
        ):
            if self.runs is not None:
                self.runs.append(list(argv))
        else:
            self.runs = None
        if any(
            k.arg not in {"args", "shell", "text", "capture_output", "check", "encoding", "timeout"}
            for k in node.keywords
        ):
            self.uncertain()

    def opened(self, node: ast.Call, path: ast.AST | None, position: int) -> None:
        if any(
            k.arg not in {"file", "mode", "buffering", "encoding", "errors", "newline", "closefd"}
            for k in node.keywords
        ):
            self.uncertain()
        operand = self.operand(node, position, "mode")
        mode = self.value(operand) if operand is not None else "r"
        if not isinstance(mode, str) or not mode or any(c not in "rwax+bt" for c in mode):
            self.dynamic = True
            return
        if "r" in mode or "+" in mode:
            self.path(path)
        if any(c in mode for c in "wax+"):
            self.path(path, write=True)

    def method(self, node: ast.Call, receiver: ast.AST, method: str) -> bool:
        base = self.value(receiver)
        if isinstance(base, FilePath) and method in (
            "read_text",
            "read_bytes",
            "write_text",
            "write_bytes",
            "open",
            "joinpath",
        ):
            if method == "open":
                self.opened(node, receiver, 0)
            elif method != "joinpath":
                self.path(receiver, write=method.startswith("write"))
            return True
        if isinstance(base, FileHandle) and method in ("read", "readlines", "write", "close"):
            return True
        if (
            isinstance(base, (str, bytes, list, tuple, dict, Data))
            and not isinstance(base, FilePath)
            and method in DATA_METHODS
        ):
            if method in ("append", "extend", "update", "pop"):
                self.mutate(receiver)
            return True
        return False

    def local_call(self, node: ast.Call, function: ast.FunctionDef) -> None:
        starts = len(self.runs) if self.runs is not None else 0
        saved = self.values.copy()
        self.values.pop(function.name, None)
        for parameter, argument in zip(function.args.args, node.args, strict=False):
            self.values[parameter.arg] = self.value(argument)
        for statement in function.body:
            self.visit(statement)
        self.values = saved
        if self.runs is not None and len(self.runs) != starts:
            self.runs = None

    def pure_call(self, node: ast.Call) -> None:
        if any(
            k.arg
            not in {
                "sep",
                "end",
                "flush",
                "sort_keys",
                "indent",
                "ensure_ascii",
                "separators",
                "reverse",
            }
            for k in node.keywords
        ):
            self.uncertain()

    def mutating_call(self, receiver: ast.AST | None, method: str) -> None:
        if (
            receiver is not None
            and isinstance(self.value(receiver), (list, tuple, dict, set))
            and method not in ("items", "keys", "values", "get", "copy", "index", "count")
        ):
            self.mutate(receiver)

    def visit_Call(self, node: ast.Call) -> None:
        name = self.name(node.func)
        receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
        method = node.func.attr if isinstance(node.func, ast.Attribute) else ""
        function = self.values.get(node.func.id) if isinstance(node.func, ast.Name) else None
        self.mutating_call(receiver, method)
        if name in PROCESS_CALLS:
            self.process(node)
        elif name in ("open", "io.open", "builtins.open"):
            self.opened(node, self.operand(node, 0, "file"), 1)
        elif name in ("Path", "pathlib.Path"):
            if self.value(node) is None:
                self.dynamic = True
        elif name in PURE_CALLS:
            self.pure_call(node)
        elif receiver is not None and self.method(node, receiver, method):
            pass
        elif isinstance(function, ast.FunctionDef):
            self.local_call(node, function)
        else:
            self.uncertain()
        # Visit operands without mistaking a known callable for a stored one.
        if receiver is not None and name not in PROCESS_CALLS and name not in PURE_CALLS:
            self.visit(receiver)
        for argument in (*node.args, *(k.value for k in node.keywords)):
            self.visit(argument)


def script_effects(
    program: str, name: str
) -> tuple[list[str], list[str], list[list[str]] | None, bool]:
    if name.startswith(("python", "pypy")):
        try:
            tree = ast.parse(program)
        except (SyntaxError, ValueError):
            return [], [], None, True
        reader = PythonEffects()
        reader.visit(tree)
        return reader.reads, reader.writes, reader.runs, reader.dynamic
    # No JavaScript parser is available in the standard library. Do not infer absence
    # of effects from a search for familiar call names.
    return [], [], None, True
