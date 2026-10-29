"""Keep run roots unlistable, with shared leases and cleanup after the runner dies."""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


class RootLease:
    """Two file locks serialize mode changes and keep overlapping runs sealed."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.control = self.open(".session-mode")
        try:
            self.lease = self.open(".session-lease")
        except BaseException:
            self.control.close()
            raise

    def open(self, name: str):
        return os.fdopen(
            os.open(self.root / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600), "r+b"
        )

    def state(self) -> dict[str, Any]:
        self.control.seek(0)
        raw = self.control.read()
        return json.loads(raw) if raw else {}

    def write(self, value: dict[str, Any]) -> None:
        self.control.seek(0)
        self.control.truncate()
        self.control.write(json.dumps(value).encode("utf-8"))
        self.control.flush()

    def enter(self) -> RootLease:
        import fcntl

        with self.locked():
            try:
                fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                state = self.state()
                mode = state["mode"] if state.get("active") else self.root.stat().st_mode & 0o7777
                self.write({"mode": mode, "active": True})
                self.root.chmod(0o311)
            fcntl.flock(self.lease, fcntl.LOCK_SH)
        return self

    @contextlib.contextmanager
    def locked(self):
        import fcntl

        fcntl.flock(self.control, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(self.control, fcntl.LOCK_UN)

    def close(self) -> None:
        import fcntl

        try:
            with self.locked():
                fcntl.flock(self.lease, fcntl.LOCK_UN)
                try:
                    fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return
                state = self.state()
                self.root.chmod(state["mode"])
                self.write({**state, "active": False})
        finally:
            self.lease.close()
            self.control.close()


class SourceLease(RootLease):
    """Shared calls seal sources; exclusive runner reads restore them, including stale seals."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        folder = self.root.parent.parent / ".agents" / "fixture-seals"
        folder.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(str(self.root).encode()).hexdigest()
        self.record = folder / (key + ".json")
        self.control = os.fdopen(
            os.open(folder / (key + ".mode"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600),
            "r+b",
        )
        self.lease = os.fdopen(
            os.open(folder / (key + ".lease"), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600),
            "r+b",
        )

    def state(self) -> dict[str, Any]:
        try:
            return json.loads(self.record.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def write(self, value: dict[str, Any]) -> None:
        # The lock inode stays in place. A crash cannot leave a truncated recovery record.
        with tempfile.NamedTemporaryFile(dir=self.record.parent, delete=False) as handle:
            pending = Path(handle.name)
            try:
                handle.write(json.dumps(value).encode("utf-8"))
                handle.flush()
                os.fsync(handle.fileno())
                os.fchmod(handle.fileno(), 0 if value.get("active") else 0o600)
                os.replace(pending, self.record)
            finally:
                pending.unlink(missing_ok=True)

    def restore(self) -> None:
        # Call leaders inherit the lease; orphaned group members must also stop before recovery.
        from evals.processes import stop_call_group

        for marker in self.record.parent.glob(self.record.stem + ".call-*"):
            stop_call_group(int(marker.name.rsplit("-", 1)[1]))
            marker.unlink()
        if self.record.exists():
            self.record.chmod(0o600)
        state = self.state()
        if state.get("active"):
            mode_held = self.root.stat().st_mode & 0o7777 == 0
            self.root.chmod(state["mode"])
            held = mode_held and tree_state(self.root) == state["tree"]
            self.write(
                {
                    **state,
                    "active": False,
                    "checks": {**state.get("checks", {}), state["epoch"]: held},
                }
            )

    def release(self) -> None:
        self.lease.close()
        self.control.close()


def tree_state(root: Path) -> dict[str, Any]:
    """Modes and content, including directory entries and symbolic links."""
    state = {}
    for path in [root, *sorted(root.rglob("*"))]:
        info = path.lstat()
        value = (
            "link:" + os.readlink(path)
            if path.is_symlink()
            else "directory"
            if path.is_dir()
            else hashlib.sha256(path.read_bytes()).hexdigest()
        )
        state[str(path.relative_to(root))] = [info.st_mode & 0o7777, value]
    return state


def fixture_links(workspace: Path, sources: Path) -> list[str]:
    """Setup may copy inputs, but may not leave a symbolic or hard link to them."""
    inodes = {
        (info.st_dev, info.st_ino)
        for path in sources.rglob("*")
        if path.is_file()
        for info in [path.stat()]
    }
    links = []
    for path in workspace.rglob("*"):
        if path.is_symlink():
            target = path.resolve()
            if target.is_relative_to(sources.resolve()) or sources.resolve().is_relative_to(target):
                links.append(str(path.relative_to(workspace)))
        elif path.is_file():
            info = path.stat()
            if (info.st_dev, info.st_ino) in inodes:
                links.append(str(path.relative_to(workspace)))
    return sorted(links)


def require_seals(
    protected: tuple[Path, ...], seals: tuple[Path, ...], extras: dict[str, Any]
) -> None:
    """A declared protected path must be covered before a call starts."""
    uncovered = sorted(
        {
            str(path)
            for path in protected
            if not any(
                path.resolve().is_relative_to(seal.resolve()) and seal.stat().st_mode & 0o7777 == 0
                for seal in seals
            )
        }
    )
    if uncovered:
        error = "protected paths have no seal: " + ", ".join(uncovered)
        extras.update(void="runner", error=error)
        extras.setdefault("isolation", []).append(["seal-coverage", "FAIL", error])
        raise ValueError(error)


_source_reads: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "fixture_source_reads", default=()
)
_source_seals: contextvars.ContextVar[tuple[SourceLease, ...]] = contextvars.ContextVar(
    "fixture_source_seals", default=()
)


def _acquire(handle: Any, mode: int, extras: dict[str, Any] | None) -> None:
    import fcntl

    started = time.monotonic()
    fcntl.flock(handle, mode)
    if extras is not None:
        extras["seal_wait_seconds"] = extras.get("seal_wait_seconds", 0.0) + (
            time.monotonic() - started
        )


@contextlib.contextmanager
def stage_access(stage: Path):
    """A staged copy is readable only while its runner holds exclusive source access."""
    if not _source_reads.get():
        raise ValueError("stage access needs exclusive fixture source access")
    stage.chmod(0o700)
    try:
        yield
    finally:
        stage.chmod(0)


@contextlib.contextmanager
def call_gate(command: list[str], kwargs: dict[str, Any]):
    """Register a call's group before it can execute; preserve its lease after runner death."""
    leases = _source_seals.get()
    if not leases:
        yield command, kwargs, lambda pid: None
        return
    read, write = os.pipe()
    try:
        descriptors = (*kwargs.get("pass_fds", ()), read, *(s.lease.fileno() for s in leases))

        def launch(pid: int) -> None:
            for lease in leases:
                lease.record.with_suffix(".call-" + str(pid)).touch()
            os.write(write, b"1")

        yield (
            [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--call",
                str(read),
                *command,
            ],
            {**kwargs, "pass_fds": descriptors},
            launch,
        )
    finally:
        os.close(read)
        os.close(write)


@contextlib.contextmanager
def source_access(root: Path, extras: dict[str, Any] | None = None):
    """Runner source reads wait for active calls; nested reads share their exclusive lease."""
    if os.name != "posix":
        yield
        return
    import fcntl

    key = str(root.resolve())
    if key in _source_reads.get():
        yield
        return
    lease = SourceLease(root)
    token = _source_reads.set((*_source_reads.get(), key))
    try:
        _acquire(lease.lease, fcntl.LOCK_EX, extras)
        with lease.locked():
            lease.restore()
        yield
    finally:
        _source_reads.reset(token)
        lease.release()


@contextlib.contextmanager
def sealed_sources(root: Path, extras: dict[str, Any]):
    """Every call shares a seal. Integrity is checked before exclusive source access resumes."""
    import fcntl

    if str(root.resolve()) in _source_reads.get():
        raise ValueError("a harness call cannot hold runner source access")
    lease = SourceLease(root)
    before = None
    mode_held = False
    token = None
    try:
        _acquire(lease.lease, fcntl.LOCK_SH, extras)
        with lease.locked():
            if root.stat().st_mode & 0o7777:
                state = lease.state()
                state = {
                    "active": True,
                    "mode": root.stat().st_mode & 0o7777,
                    "tree": tree_state(root),
                    "epoch": str(root.stat().st_ctime_ns),
                    "checks": state.get("checks", {}),
                }
                # Keep the restoration mode before chmod, including a crash between the writes.
                lease.write(state)
                root.chmod(0)
                state["epoch"] = str(root.stat().st_ctime_ns)
                lease.write(state)
            before = str(root.stat().st_ctime_ns)
            if root.stat().st_mode & 0o7777:
                raise ValueError("fixture source seal was changed")
        try:
            token = _source_seals.set((*_source_seals.get(), lease))
            yield
        finally:
            if token is not None:
                _source_seals.reset(token)
            mode_held = root.stat().st_mode & 0o7777 == 0
    finally:
        # Do not open the sources while any peer's harness is still running.
        fcntl.flock(lease.lease, fcntl.LOCK_UN)
        _acquire(lease.lease, fcntl.LOCK_EX, extras)
        try:
            with lease.locked():
                lease.restore()
                # Peers share the check taken before runner reads resume. A later
                # setup may legitimately write bytecode or start another seal.
                held = (
                    mode_held and before is not None and lease.state()["checks"].get(before, False)
                )
            extras.setdefault("isolation", []).append(
                ["fixture-source-seal", "PASS" if held else "FAIL", "source modes and content"]
            )
            if not held:
                extras.update(
                    void="contaminated", error="the run changed fixture sources or their seal"
                )
        finally:
            lease.release()


def _guard() -> None:
    request = json.loads(sys.stdin.readline())
    stage = Path(request["stage"])
    mode = stage.stat().st_mode & 0o7777
    with contextlib.ExitStack() as stack:
        stack.callback(stage.chmod, mode)
        roots = [Path(word) for word in request["roots"]]
        for root in roots:
            lease = RootLease(root)
            stack.callback(lease.close)
            lease.enter()
        print("ready", flush=True)
        # The pipe closes on normal exit, a crash or an uncatchable signal in the runner.
        sys.stdin.read()
        changed = [str(root) for root in roots if root.stat().st_mode & 0o7777 != 0o311]
    print(json.dumps({"changed": changed}), flush=True)


def isolation_rows(harness: str) -> list[list[str]]:
    return (
        [
            [
                "root-permissions",
                "UNVERIFIED",
                "modes do not stop owner chmod; sandbox enforcement is unverified",
            ]
        ]
        if harness == "claude-code"
        else []
    )


def _roots(paths: tuple[Path, ...]) -> list[Path]:
    roots = sorted({path.resolve() for path in paths})
    shared = {Path(tempfile.gettempdir()).resolve(), Path("/"), Path.home().resolve()}
    if os.name != "posix" or any(root in shared for root in roots):
        raise ValueError("session isolation needs dedicated POSIX workspace and results roots")
    return roots


@contextlib.contextmanager
def sealed_roots(paths: tuple[Path, ...], stage: Path, extras: dict[str, Any]):
    """A separate session restores modes even after SIGKILL of the runner's process group."""
    roots = _roots(paths)
    child = subprocess.Popen(
        [sys.executable, "-I", "-B", str(Path(__file__).resolve())],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        start_new_session=True,
    )
    try:
        if child.stdin is None or child.stdout is None:
            raise ValueError("session permission guard has no pipes")
        child.stdin.write(json.dumps({"roots": list(map(str, roots)), "stage": str(stage)}) + "\n")
        child.stdin.flush()
        if child.stdout.readline().strip() != "ready":
            raise ValueError("session permission guard did not seal the roots")
        yield
    finally:
        if child.stdin is not None:
            child.stdin.close()
            child.stdin = None
        output, error = child.communicate(timeout=30)
        if child.returncode:
            raise ValueError(f"session permission cleanup failed: {error}")
        if json.loads(output)["changed"]:
            extras.update(void="contaminated", error="the run changed root permissions")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--call"]:
        if os.read(int(sys.argv[2]), 1) != b"1":
            raise SystemExit("runner closed the call gate")
        os.close(int(sys.argv[2]))
        code = subprocess.run(sys.argv[3:], close_fds=False).returncode
        if code < 0:
            os.kill(os.getpid(), -code)
        raise SystemExit(code)
    else:
        _guard()
