"""The checks OutcomeBound adds to Ponytail's agentic benchmark.

Ponytail's benchmark (https://github.com/DietrichGebert/ponytail, MIT) scores its repo-feature
(`tmpl-*`) and open (`open-*`, `vibe-*`) tasks by size only: a pass means a new file exists or the
Python compiles. The patched `run.py` loads this file with `--ob-checks` and calls, inside its own
`score_workspace`:

- `oracle(task_id, workdir, answer, git)`: a completion check of our own for those tasks. It returns
  None where it has no check for the task, else `{"correct": 1 | 0 | None, "reason": ...}`; None
  means it could not decide (a module that is not installed, an interface it could not drive), and
  then the upstream verdict stands and the reason says so. `git(*args)` runs git against the cell's
  evidence clone of the baseline, with the workspace as work tree.
- `loading_check(arm, events)`: what the CLI's stream-JSON start event says was loaded.

The repo-feature checks are static (the template's frontend and backend dependencies are not
installed, and Bash is blocked for the agent, so nothing is built); the open-task checks run the
produced script in a subprocess with a timeout, as Ponytail's own hidden checks run produced code.
Standard library only. `REFERENCES` holds a passing and a failing outcome for every check; the
driver's selftest applies each one through Ponytail's real scoring path.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT = 20

# ---------------------------------------------------------------- repo features: backend


def _changed(git, prefix: str, suffixes: tuple[str, ...]) -> list[tuple[str, str]]:
    """(status, path) of files the agent added or modified under `prefix`, against the baseline."""
    git("add", "-A")
    out = []
    for line in git("diff", "--cached", "--name-status", "HEAD").splitlines():
        parts = line.split("\t")
        if (
            len(parts) >= 2
            and parts[0][:1] in "AM"
            and parts[-1].startswith(prefix)
            and parts[-1].endswith(suffixes)
        ):
            out.append((parts[0][:1], parts[-1]))
    return out


def _routes(text: str) -> dict[tuple[str, str, str], str]:
    """(method, path, function) -> source, for each FastAPI route a module defines."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and dec.func.attr in ("get", "post", "put", "patch", "delete")
            ):
                path = (
                    dec.args[0].value if dec.args and isinstance(dec.args[0], ast.Constant) else ""
                )
                found[(dec.func.attr, str(path), node.name)] = (
                    ast.get_source_segment(text, node) or ""
                )
    return found


def _new_routes(workdir: Path, git) -> list[tuple[str, str, str]]:
    """(method, path, source) of routes that are new or changed against the baseline."""
    new = []
    for status, rel in _changed(git, "backend/app/", (".py",)):
        text = (workdir / rel).read_text(encoding="utf-8", errors="replace")
        before = _routes(git("show", f"HEAD:{rel}")) if status == "M" else {}
        for key, src in _routes(text).items():
            if before.get(key) != src:
                new.append((key[0], key[1], src))
    return new


def _user_scoped(src: str) -> bool:
    return "current_user" in src or "CurrentUser" in src


BACKEND = {
    "tmpl-be-duplicate": (
        "a POST route that adds a copy of an item",
        lambda m, p, s: m == "post" and "{" in p and "session.add" in s and "Item" in s,
    ),
    "tmpl-be-search": (
        "a GET route that matches item titles",
        lambda m, p, s: (
            m == "get"
            and "title" in s
            and re.search(r"\.(i?like|contains|startswith)\(|\bin\s+\w+\.title|\.find\(", s)
        ),
    ),
    "tmpl-be-count": (
        "a GET route that counts the user's items",
        lambda m, p, s: (
            m == "get" and re.search(r"func\.count|\.count\(|len\(", s) and "owner_id" in s
        ),
    ),
    "tmpl-be-bulkdelete": (
        "a route that deletes a list of the user's items",
        lambda m, p, s: (
            m in ("delete", "post")
            and "session.delete" in s
            and re.search(r"list\[|List\[|\bids\b", s)
            and "owner_id" in s
        ),
    ),
    "tmpl-be-csv": (
        "a GET route that returns the user's items as CSV",
        lambda m, p, s: m == "get" and "csv" in s.lower() and "text/csv" in s and "owner_id" in s,
    ),
}


def _backend(task_id: str, workdir: Path, git):
    routes = _new_routes(workdir, git)
    if task_id == "tmpl-be-archive":
        models = (workdir / "backend/app/models.py").read_text(encoding="utf-8", errors="replace")
        field = re.search(r"^\s+(is_)?archived?\w*\s*:\s*bool", models, re.MULTILINE)
        exposed = any("archiv" in (p + s).lower() and _user_scoped(s) for _m, p, s in routes)
        ok = bool(field) and exposed
        return {
            "correct": int(ok),
            "reason": "archive field on the item model and a user-scoped route that sets it"
            if ok
            else f"archive: model field {'found' if field else 'missing'}, "
            f"route {'found' if exposed else 'missing'}",
        }
    what, test = BACKEND[task_id]
    ok = any(test(m, p, s) and _user_scoped(s) for m, p, s in routes)
    return {
        "correct": int(ok),
        "reason": f"{'found' if ok else 'missing'}: {what}, scoped to the user; "
        f"{len(routes)} new route(s)",
    }


# ---------------------------------------------------------------- repo features: frontend

FRONTEND = {
    "tmpl-fe-datepicker": (
        "a date input",
        [r"type=[\"']date[\"']|<Calendar|DayPicker|getDate\(|daysIn", r"onChange|onSelect"],
    ),
    "tmpl-fe-colorpicker": (
        "a color input",
        [r"type=[\"']color[\"']|#[0-9a-fA-F]{6}|hsl\(", r"onChange"],
    ),
    "tmpl-fe-command": (
        "a filtered command list opened from the keyboard",
        [r"\.filter\(", r"onKeyDown|keydown", r"[\"']k[\"']|metaKey|ctrlKey"],
    ),
    "tmpl-fe-dropzone": (
        "a drop target that takes files",
        [r"onDrop", r"dataTransfer|type=[\"']file[\"']", r"preventDefault"],
    ),
    "tmpl-fe-wizard": (
        "steps with next and back",
        [r"set\w*Step\w*\(|step\s*[+-]\s*1", r"[Nn]ext", r"[Bb]ack|[Pp]rev"],
    ),
    "tmpl-fe-rating": (
        "five stars that set a value",
        [
            r"[Ss]tar",
            r"\[1,\s*2,\s*3,\s*4,\s*5\]|length:\s*5|max\w*\s*=\s*5|max\w*\s*:\s*\w*\s*=?\s*5|Array\(5\)|<\s*=?\s*5",
            r"onChange|onRate|setValue|setRating",
        ],
    ),
}


def _frontend(task_id: str, workdir: Path, git):
    texts = []
    for status, rel in _changed(git, "frontend/src/", (".tsx", ".ts", ".jsx", ".js")):
        if status == "A":
            texts.append((workdir / rel).read_text(encoding="utf-8", errors="replace"))
        else:
            diff = git("diff", "--cached", "-U0", "HEAD", "--", rel)
            texts.append(
                "\n".join(
                    line[1:]
                    for line in diff.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
            )
    code = "\n".join(texts)
    what, patterns = FRONTEND[task_id]
    missing = [p for p in patterns if not re.search(p, code)]
    exported = re.search(
        r"\bexport\s+(default\s+)?(function|const|class)\b|\bexport\s+default\b|\bexport\s*\{", code
    )
    ok = bool(code) and not missing and bool(exported)
    return {
        "correct": int(ok),
        "reason": f"{what}: {'found' if ok else 'missing'}"
        + (
            "" if ok else f" ({'no export' if not exported else len(missing)} pattern(s) unmatched)"
        ),
    }


# ---------------------------------------------------------------- open requests

FENCE = re.compile(r"```[a-zA-Z0-9_+-]*\r?\n(.*?)```", re.S)


def _python(workdir: Path, answer: str) -> str:
    """The Python the agent delivered: its .py files, else the code blocks of its answer."""
    files = [
        p
        for p in sorted(workdir.rglob("*.py"))
        if ".git" not in p.parts
        and "__pycache__" not in p.parts
        and not p.name.startswith(("_", "."))
    ]
    if files:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in files)
    return "\n".join(FENCE.findall(answer or ""))


def _run(workdir: Path, script: str, args: list[str], stdin: str = "", files: dict | None = None):
    """Run a delivered script in a throwaway copy of the workspace; (exit, output), or None on a
    timeout."""
    with tempfile.TemporaryDirectory(prefix="ob-oracle-") as folder:
        tmp = Path(folder)
        for p in workdir.glob("*.py"):
            shutil.copy2(p, tmp / p.name)
        for name, content in (files or {}).items():
            (tmp / name).write_text(content, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp), "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            done = subprocess.run(
                [sys.executable, *script_args(script, args)],
                cwd=tmp,
                input=stdin,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                encoding="utf-8",
            )
        except subprocess.TimeoutExpired:
            return None
        return done.returncode, done.stdout + done.stderr


def script_args(script: str, args: list[str]) -> list[str]:
    """A probe (text starting `#probe`) runs with -c; a delivered script runs by its file name."""
    return ["-c", script, *args] if script.startswith("#probe") else [script, *args]


def _missing_module(output: str) -> str | None:
    m = re.search(r"ModuleNotFoundError: No module named '([\w.]+)'", output)
    return m.group(1) if m else None


# A probe imports the delivered module (stdin closed, so a top-level prompt fails rather than
# waits) and drives the functions or classes it finds by name; it prints one JSON line.
PROBE = r"""#probe
import importlib.util, inspect, json, sys
spec = importlib.util.spec_from_file_location("delivered", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mod)
except SystemExit:
    pass
def candidates(words):
    out = []
    for name, obj in vars(mod).items():
        if name.startswith("_") or getattr(obj, "__module__", None) != "delivered":
            continue
        if inspect.isfunction(obj) and any(w in name.lower() for w in words):
            out.append(obj)
        if inspect.isclass(obj):
            try:
                inst = obj()
            except Exception:
                continue
            for mname, meth in inspect.getmembers(inst, inspect.ismethod):
                if not mname.startswith("_") and any(w in mname.lower() for w in words):
                    out.append(meth)
    return out
def call(f, *a):
    try:
        return True, f(*a)
    except Exception as e:
        return False, repr(e)
TASK = sys.argv[2]
"""

PROBES = {
    "vibe-password": PROBE
    + r"""
weak, strong = "password", "Xq7#mP2!vL9@wR4z"
def rank(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)): return v
    if isinstance(v, dict):
        for k in ("score", "strength", "points", "entropy"):
            if isinstance(v.get(k), (int, float)) and not isinstance(v.get(k), bool): return v[k]
        v = " ".join(map(str, v.values()))
    if isinstance(v, (tuple, list)):
        nums = [x for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if nums: return nums[0]
        v = " ".join(map(str, v))
    s = str(v).lower()
    order = ["very strong", "strong", "good", "moderate", "medium", "fair", "very weak", "weak"]
    score = {"very weak": 0, "weak": 1, "fair": 2, "medium": 2, "moderate": 2, "good": 3,
             "strong": 4, "very strong": 5}
    for w in order:
        if w in s: return score[w]
    return None
verdict = None
words = ("strength", "check", "score", "evaluate", "rate", "assess", "analy", "password")
for f in candidates(words):
    ok1, a = call(f, weak); ok2, b = call(f, strong)
    if ok1 and ok2 and rank(a) is not None and rank(b) is not None:
        verdict = {"correct": int(rank(b) > rank(a)),
                   "reason": f"{f.__name__}: weak {rank(a)}, strong {rank(b)}"}
        break
print(json.dumps(verdict))
""",
    "vibe-shortener": PROBE
    + r"""
url = "https://example.com/some/long/path?q=1"
verdict = None
shorts = candidates(("shorten", "encode", "create", "add", "make", "short"))
backs = candidates(("expand", "resolve", "decode", "lookup", "original", "redirect", "get", "long",
                    "retrieve"))
for s in shorts:
    ok, code = call(s, url)
    if not ok or not isinstance(code, str): continue
    for b in backs:
        if getattr(b, "__self__", None) is not getattr(s, "__self__", None): continue
        for key in (code, code.rstrip("/").rsplit("/", 1)[-1]):
            ok, back = call(b, key)
            if ok and back == url:
                verdict = {"correct": 1,
                           "reason": f"{s.__name__} then {b.__name__} round-trips the URL"}
                break
        if verdict: break
    if verdict: break
if verdict is None and shorts and backs:
    verdict = {"correct": 0, "reason": "shorten/expand found, no round trip"}
print(json.dumps(verdict))
""",
    "vibe-md2html": PROBE
    + r"""
md = "# Title\n\nSome **bold** text.\n"
verdict = None
for f in candidates(("convert", "html", "render", "markdown", "parse", "md")):
    ok, out = call(f, md)
    if ok and isinstance(out, str) and "<" in out:
        good = "<h1" in out.lower() and ("<strong" in out.lower() or "<b>" in out.lower())
        verdict = {"correct": int(good), "reason": f"{f.__name__}: heading and bold "
                   + ("rendered" if good else "not rendered")}
        break
print(json.dumps(verdict))
""",
}

CSV = "name,amount\na,1\nb,2\nc,3\nd,4\n"


def _dataclass(code: str, answer: str):
    feats = [
        f
        for f in (
            "field(",
            "frozen=True",
            "order=True",
            "__post_init__",
            "asdict",
            "default_factory",
            "replace(",
        )
        if f in code
    ]
    ok = "@dataclass" in code and len(feats) >= 2
    return {"correct": int(ok), "reason": f"@dataclass with {len(feats)} feature(s) shown"}


def _decorators(code: str, answer: str):
    ok = False
    for block in [code, *FENCE.findall(answer or "")]:
        try:
            tree = ast.parse(block)
        except SyntaxError:
            continue
        makers = {
            n.name
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)
            and any(isinstance(c, ast.FunctionDef) for c in n.body)
            and any(
                isinstance(r, ast.Return) and isinstance(r.value, ast.Name) for r in ast.walk(n)
            )
        }
        used = {
            d.id if isinstance(d, ast.Name) else getattr(d.func, "id", None)
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))
            for d in n.decorator_list
            if isinstance(d, (ast.Name, ast.Call))
        }
        ok = ok or bool(makers & used)
    return {
        "correct": int(ok),
        "reason": "a decorator defined and applied"
        if ok
        else "no decorator both defined and applied",
    }


def _mandelbrot(code: str, answer: str):
    escape = re.search(
        r"abs\(\s*z\s*\)\s*>=?\s*2|>\s*=?\s*4(\.0)?\b|\.real\s*\*\*\s*2|z\s*\*\s*z\s*\+\s*c"
        r"|z\*\*2\s*\+\s*c",
        code,
    )
    shown = re.search(r"imshow|savefig|\.save\(|print\(|\.show\(|write\(", code)
    ok = bool(escape and shown)
    return {
        "correct": int(ok),
        "reason": f"escape-time iteration {'found' if escape else 'missing'}, "
        f"output {'found' if shown else 'missing'}",
    }


def _langgraph(code: str, answer: str):
    ok = (
        "langgraph" in code
        and re.search(r"StateGraph|create_react_agent|MessageGraph", code)
        and ("create_react_agent" in code or ("add_node" in code and "compile(" in code))
    )
    return {
        "correct": int(bool(ok)),
        "reason": "a LangGraph graph built and compiled"
        if ok
        else "no LangGraph graph built and compiled",
    }


# The open tasks whose check reads the delivered code without running it.
STATIC = {
    "open-dataclass": _dataclass,
    "open-decorators": _decorators,
    "open-mandelbrot": _mandelbrot,
    "vibe-langgraph": _langgraph,
}


def _csvstats(workdir: Path, script: str):
    done = _run(workdir, script, ["data.csv"], files={"data.csv": CSV})
    if done is None:
        return {"correct": 0, "reason": "timed out on a stated CSV"}
    missing = _missing_module(done[1])
    if missing:
        return {"correct": None, "reason": f"undecided: needs {missing}, not installed"}
    ok = done[0] == 0 and "2.5" in done[1]
    return {
        "correct": int(ok),
        "reason": f"on a stated CSV: exit {done[0]}, "
        f"mean {'shown' if '2.5' in done[1] else 'not shown'}",
    }


def _todo(workdir: Path, script: str):
    ran = None
    for add, show in (
        (["add", "buy milk"], ["list"]),
        (["--add", "buy milk"], ["--list"]),
        (["-a", "buy milk"], ["-l"]),
    ):
        with tempfile.TemporaryDirectory(prefix="ob-todo-") as keep:
            first = _run_in(workdir, script, add, keep)
            second = _run_in(workdir, script, show, keep)
        if first and second and first[0] == 0 and second[0] == 0:
            if "buy milk" in second[1]:
                return {"correct": 1, "reason": f"`{add[0]}` then `{show[0]}` lists the item"}
            ran = ran or f"`{add[0]}` then `{show[0]}` ran, the item is not listed"
        if first and _missing_module(first[1]):
            return {
                "correct": None,
                "reason": f"undecided: needs {_missing_module(first[1])}, not installed",
            }
    if ran:
        return {"correct": 0, "reason": ran}
    return {
        "correct": None,
        "reason": "undecided: no add/list command found to drive "
        "(an interactive app is not driven)",
    }


def _open(task_id: str, workdir: Path, answer: str):
    if task_id in STATIC:
        return STATIC[task_id](_python(workdir, answer), answer)
    script = {
        "vibe-todo": "todo.py",
        "vibe-password": "password.py",
        "vibe-shortener": "shortener.py",
        "vibe-md2html": "md2html.py",
        "vibe-csvstats": "csvstats.py",
    }[task_id]
    if not (workdir / script).is_file():
        return {"correct": 0, "reason": f"no {script}"}
    if task_id == "vibe-csvstats":
        return _csvstats(workdir, script)
    if task_id == "vibe-todo":
        return _todo(workdir, script)
    done = _run(workdir, PROBES[task_id], [str(workdir / script), task_id])
    if done is None:
        return {"correct": 0, "reason": "timed out on import"}
    missing = _missing_module(done[1])
    if missing:
        return {"correct": None, "reason": f"undecided: needs {missing}, not installed"}
    try:
        verdict = json.loads(done[1].strip().splitlines()[-1])
    except (ValueError, IndexError):
        verdict = None
    return verdict or {"correct": None, "reason": "undecided: no function found to drive"}


def _run_in(workdir: Path, script: str, args: list[str], keep: str):
    """Like `_run`, but in one folder kept across calls, so a todo app's store survives."""
    keep_path = Path(keep)
    for p in workdir.glob("*.py"):
        if not (keep_path / p.name).exists():
            shutil.copy2(p, keep_path / p.name)
    env = {"PATH": os.environ.get("PATH", ""), "HOME": keep, "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        done = subprocess.run(
            [sys.executable, script, *args],
            cwd=keep,
            input="",
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            encoding="utf-8",
        )
    except subprocess.TimeoutExpired:
        return None
    return done.returncode, done.stdout + done.stderr


OPEN = (
    "open-dataclass",
    "open-decorators",
    "open-mandelbrot",
    "vibe-todo",
    "vibe-password",
    "vibe-shortener",
    "vibe-md2html",
    "vibe-csvstats",
    "vibe-langgraph",
)


def oracle(task_id: str, workdir, answer: str, git):
    workdir = Path(workdir)
    if task_id in BACKEND or task_id == "tmpl-be-archive":
        return _backend(task_id, workdir, git)
    if task_id in FRONTEND:
        return _frontend(task_id, workdir, git)
    if task_id in OPEN:
        return _open(task_id, workdir, answer)
    return None


# ---------------------------------------------------------------- loading check

OB_SKILLS = ("using-outcomebound", "diagnose", "tests-worth-keeping")


def loading_check(arm: str, events: list) -> dict:
    """What the stream-JSON start event says was loaded. It names plugins and skills; whether it
    names instruction files and hooks is UNVERIFIED until a real cell, so a missing field is
    UNVERIFIED, never a pass. A foreign marker (Ponytail in a non-ponytail cell, OB's skills in a
    non-ob cell) fails."""
    init = next(
        (
            e
            for e in events
            if isinstance(e, dict) and e.get("type") == "system" and e.get("subtype") == "init"
        ),
        None,
    )
    if init is None:
        return {"status": "UNVERIFIED", "reason": "no start event"}
    plugins = [p.get("name") if isinstance(p, dict) else str(p) for p in init.get("plugins") or []]
    names = [
        str(s.get("name") if isinstance(s, dict) else s)
        for s in (init.get("skills") or []) + (init.get("slash_commands") or [])
    ]
    has_ponytail = any("ponytail" in (p or "").lower() for p in plugins)
    has_ob = any(n.split(":")[-1] in OB_SKILLS for n in names)
    seen = {
        "plugins": plugins,
        "ob_skills": has_ob,
        "fields": sorted(k for k in ("plugins", "skills", "slash_commands") if k in init),
    }
    if (has_ponytail and arm != "ponytail") or (has_ob and arm != "ob"):
        return {"status": "FAIL", "reason": "a foreign arm's plugin or skills loaded", **seen}
    if "plugins" not in init and "skills" not in init:
        return {
            "status": "UNVERIFIED",
            "reason": "start event names neither plugins nor skills",
            **seen,
        }
    own = {"ponytail": has_ponytail, "ob": has_ob}.get(arm, True)
    return {
        "status": "PASS" if own else "FAIL",
        "reason": "own marker present, no foreign one" if own else "own marker missing",
        "instruction_files": "UNVERIFIED",
        **seen,
    }


# ---------------------------------------------------------------- references for the selftest
# Each is a set of edits to the built cell: ("write", path, text), ("append", path, text) or
# ("replace", path, old, new). "good" must pass the oracle, "bad" must fail it.

ROUTE = '\n\n@router.{m}("{p}")\ndef {name}({params}) -> Any:\n{body}\n'
P_USER = "session: SessionDep, current_user: CurrentUser"
ITEMS = "backend/app/api/routes/items.py"


def _route(m, p, name, params, body):
    return ("append", ITEMS, ROUTE.format(m=m, p=p, name=name, params=params, body=body))


STUB_ROUTE = _route("get", "/stub", "stub", P_USER, "    return None")
STUB_COMPONENT = "export function Widget() {\n  return <div />\n}\n"
COMPONENT = "frontend/src/components/Common/Widget.tsx"

REFERENCES = {
    "tmpl-be-duplicate": {
        "good": [
            _route(
                "post",
                "/{id}/duplicate",
                "duplicate_item",
                P_USER + ", id: uuid.UUID",
                "    item = session.get(Item, id)\n    if not item or item.owner_id != "
                "current_user.id:\n"
                '        raise HTTPException(status_code=404, detail="Item not found")\n'
                "    copy = Item(title=item.title, description=item.description, "
                "owner_id=current_user.id)\n"
                "    session.add(copy)\n    session.commit()\n    return copy",
            )
        ],
        "bad": [STUB_ROUTE],
    },
    "tmpl-be-search": {
        "good": [
            _route(
                "get",
                "/search",
                "search_items",
                P_USER + ", q: str",
                "    stmt = select(Item).where(Item.owner_id == current_user.id, "
                "col(Item.title).contains(q))\n"
                "    return session.exec(stmt).all()",
            )
        ],
        "bad": [_route("get", "/search", "search_items", P_USER + ", q: str", "    return []")],
    },
    "tmpl-be-count": {
        "good": [
            _route(
                "get",
                "/count",
                "count_items",
                P_USER,
                "    return "
                "session.exec(select(func.count()).select_from(Item).where(Item.owner_id == "
                "current_user.id)).one()",
            )
        ],
        "bad": [_route("get", "/count", "count_items", P_USER, "    return 0")],
    },
    "tmpl-be-archive": {
        "good": [
            (
                "replace",
                "backend/app/models.py",
                "class Item(ItemBase, table=True):\n",
                "class Item(ItemBase, table=True):\n    archived: bool = False\n",
            ),
            _route(
                "post",
                "/{id}/archive",
                "archive_item",
                P_USER + ", id: uuid.UUID",
                "    item = session.get(Item, id)\n    item.archived = True\n    "
                "session.add(item)\n"
                "    session.commit()\n    return item",
            ),
        ],
        "bad": [
            _route(
                "post",
                "/{id}/archive",
                "archive_item",
                P_USER + ", id: uuid.UUID",
                "    return None",
            )
        ],
    },
    "tmpl-be-bulkdelete": {
        "good": [
            _route(
                "delete",
                "/",
                "delete_items",
                P_USER + ", ids: list[uuid.UUID]",
                "    for item in session.exec(select(Item).where(col(Item.id).in_(ids), "
                "Item.owner_id == current_user.id)):\n"
                "        session.delete(item)\n    session.commit()\n    return "
                'Message(message="deleted")',
            )
        ],
        "bad": [
            _route(
                "delete",
                "/",
                "delete_items",
                P_USER + ", ids: list[uuid.UUID]",
                '    return Message(message="deleted")',
            )
        ],
    },
    "tmpl-be-csv": {
        "good": [
            _route(
                "get",
                "/export",
                "export_items",
                P_USER,
                "    import csv, io\n    from fastapi.responses import Response\n    buf = "
                "io.StringIO()\n"
                "    w = csv.writer(buf)\n    for item in "
                "session.exec(select(Item).where(Item.owner_id == current_user.id)):\n"
                "        w.writerow([item.id, item.title])\n    return Response(buf.getvalue(), "
                'media_type="text/csv")',
            )
        ],
        "bad": [_route("get", "/export", "export_items", P_USER, '    return ""')],
    },
    "tmpl-fe-datepicker": {
        "good": [
            (
                "write",
                COMPONENT,
                "export function DateField({ value, onChange }) {\n"
                '  return <input type="date" value={value} onChange={(e) => '
                "onChange(e.target.value)} />\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "tmpl-fe-colorpicker": {
        "good": [
            (
                "write",
                COMPONENT,
                "export function ColorField({ value, onChange }) {\n"
                '  return <input type="color" value={value} onChange={(e) => '
                "onChange(e.target.value)} />\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "tmpl-fe-command": {
        "good": [
            (
                "write",
                COMPONENT,
                'export function Palette({ commands }) {\n  const [q, setQ] = useState("")\n'
                '  useEffect(() => { const h = (e) => { if (e.metaKey && e.key === "k") '
                "setOpen(true) }\n"
                '    window.addEventListener("keydown", h); return () => '
                'window.removeEventListener("keydown", h) }, [])\n'
                "  const shown = commands.filter((c) => c.label.includes(q))\n"
                "  return <input value={q} onChange={(e) => setQ(e.target.value)} />\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "tmpl-fe-dropzone": {
        "good": [
            (
                "write",
                COMPONENT,
                "export function Drop({ onFiles }) {\n"
                "  return <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { "
                "e.preventDefault(); onFiles(e.dataTransfer.files) }} />\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "tmpl-fe-wizard": {
        "good": [
            (
                "write",
                COMPONENT,
                "export function Wizard({ steps }) {\n  const [step, setStep] = useState(0)\n"
                "  return <div>{steps[step]}<button onClick={() => setStep(step - 1)}>Back</button>"
                "<button onClick={() => setStep(step + 1)}>Next</button></div>\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "tmpl-fe-rating": {
        "good": [
            (
                "write",
                COMPONENT,
                "export function Rating({ value, onChange }) {\n"
                "  return <div>{[1, 2, 3, 4, 5].map((n) => <Star key={n} onClick={() => "
                "onChange(n)} />)}</div>\n}\n",
            )
        ],
        "bad": [("write", COMPONENT, STUB_COMPONENT)],
    },
    "open-dataclass": {
        "good": [
            (
                "write",
                "example.py",
                "from dataclasses import dataclass, field, asdict\n\n@dataclass(order=True)\n"
                "class Point:\n    x: int\n    y: int = 0\n    tags: list = "
                "field(default_factory=list)\n\nprint(asdict(Point(1)))\n",
            )
        ],
        "bad": [
            (
                "write",
                "example.py",
                "class Point:\n    def __init__(self, x):\n        self.x = x\n",
            )
        ],
    },
    "open-decorators": {
        "good": [
            (
                "write",
                "example.py",
                "def shout(fn):\n    def inner(*a):\n        return fn(*a).upper()\n    return "
                "inner\n\n"
                "@shout\ndef hi(name):\n    return 'hi ' + name\n\nprint(hi('x'))\n",
            )
        ],
        "bad": [("write", "example.py", "def hi(name):\n    return 'hi ' + name\n")],
    },
    "open-mandelbrot": {
        "good": [
            (
                "write",
                "mandel.py",
                "for y in range(-10, 11):\n    row = ''\n    for x in range(-30, 11):\n"
                "        c, z, n = complex(x / 15, y / 10), 0, 0\n        while abs(z) <= 2 and n "
                "< 30:\n"
                "            z = z * z + c\n            n += 1\n        row += '#' if n == 30 else "
                "' '\n    print(row)\n",
            )
        ],
        "bad": [("write", "mandel.py", "print('mandelbrot')\n")],
    },
    "vibe-todo": {
        "good": [
            (
                "write",
                "todo.py",
                "import json, os, sys\nPATH = os.path.join(os.path.expanduser('~'), 'todo.json')\n"
                "items = json.load(open(PATH)) if os.path.exists(PATH) else []\n"
                "if sys.argv[1] == 'add':\n    items.append(sys.argv[2]); json.dump(items, "
                "open(PATH, 'w'))\n"
                "elif sys.argv[1] == 'list':\n    print('\\n'.join(items))\n",
            )
        ],
        "bad": [
            (
                "write",
                "todo.py",
                "import sys\nif sys.argv[1] == 'list':\n    print('nothing yet')\n",
            )
        ],
    },
    "vibe-password": {
        "good": [
            (
                "write",
                "password.py",
                "def strength(p):\n    return sum([len(p) >= 12, any(c.isdigit() for c in p),"
                " any(c.isupper() for c in p), any(not c.isalnum() for c in p)])\n",
            )
        ],
        "bad": [("write", "password.py", "def strength(p):\n    return 1\n")],
    },
    "vibe-shortener": {
        "good": [
            (
                "write",
                "shortener.py",
                "_urls = {}\ndef shorten(url):\n    key = str(len(_urls))\n    _urls[key] = url\n  "
                "  return key\n"
                "def expand(key):\n    return _urls[key]\n",
            )
        ],
        "bad": [
            (
                "write",
                "shortener.py",
                "def shorten(url):\n    return 'x'\ndef expand(key):\n    return None\n",
            )
        ],
    },
    "vibe-md2html": {
        "good": [
            (
                "write",
                "md2html.py",
                "import re\ndef convert(md):\n    out = []\n    for line in md.splitlines():\n"
                "        line = re.sub(r'\\*\\*(.+?)\\*\\*', r'<strong>\\1</strong>', line)\n"
                "        if line.startswith('# '):\n            out.append('<h1>' + line[2:] + "
                "'</h1>')\n"
                "        elif line:\n            out.append('<p>' + line + '</p>')\n    return "
                "'\\n'.join(out)\n",
            )
        ],
        "bad": [("write", "md2html.py", "def convert(md):\n    return '<p>' + md + '</p>'\n")],
    },
    "vibe-csvstats": {
        "good": [
            (
                "write",
                "csvstats.py",
                "import csv, statistics, sys\nrows = list(csv.DictReader(open(sys.argv[1])))\n"
                "vals = [float(r['amount']) for r in rows]\nprint('mean', statistics.mean(vals))\n",
            )
        ],
        "bad": [
            (
                "write",
                "csvstats.py",
                "import sys\nprint('rows:', len(open(sys.argv[1]).readlines()))\n",
            )
        ],
    },
    "vibe-langgraph": {
        "good": [
            (
                "write",
                "graph.py",
                "from langgraph.graph import StateGraph, END\n\ng = StateGraph(dict)\n"
                "g.add_node('a', lambda s: s)\ng.set_entry_point('a')\ng.add_edge('a', END)\napp = "
                "g.compile()\n",
            )
        ],
        "bad": [("write", "graph.py", "print('LangGraph builds graphs of nodes')\n")],
    },
}


def apply_reference(workdir, edits) -> None:
    """Make a reference outcome in a built cell."""
    workdir = Path(workdir)
    for edit in edits:
        kind, rel = edit[0], edit[1]
        path = workdir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if kind == "write":
            path.write_text(edit[2], encoding="utf-8")
        elif kind == "append":
            path.write_text(path.read_text(encoding="utf-8") + edit[2], encoding="utf-8")
        elif kind == "replace":
            text = path.read_text(encoding="utf-8")
            if edit[2] not in text:
                raise ValueError(f"reference edit does not apply to {rel}")
            path.write_text(text.replace(edit[2], edit[3], 1), encoding="utf-8")
