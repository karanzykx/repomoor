"""Project-contained filesystem access: bounded reads and create-only writes.

This is the ONLY module allowed to write files. Every write goes through
`safe_create`, which refuses symlinks, never overwrites, and stays inside the root.
On POSIX it walks the path with directory file descriptors, so it is race-safe
against a directory being swapped for a symlink while it runs.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat

MAX_MANIFEST_BYTES = 196_608


def is_local_regular_file(root: Path, path: Path) -> bool:
    """Prevent symlinks (including parent symlinks) from escaping the repository."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    node = root
    for part in rel.parts:
        node = node / part
        if node.is_symlink():
            return False
    return path.is_file()


def local_exists(root: Path, rel: str) -> bool:
    path = root / rel
    try:
        if path.is_symlink():
            return True  # explicitly report but never follow
        node = root
        for part in Path(rel).parts:
            node = node / part
            if node.is_symlink():
                return True
        return path.exists()
    except OSError:
        return False


def read_bounded(root: Path, rel: str, limit: int = MAX_MANIFEST_BYTES) -> tuple[str | None, str | None]:
    """Return (text, None) on success, (None, None) if absent, or (None, issue) where issue is
    'not-regular-file' (symlink, directory, FIFO, ...), 'too-large' or 'unreadable'."""
    path = root / rel
    if not is_local_regular_file(root, path):
        return None, ("not-regular-file" if local_exists(root, rel) else None)
    try:
        if path.stat().st_size > limit:
            return None, "too-large"
        with open(path, "rb") as handle:
            raw = handle.read(limit + 1)
    except OSError:
        return None, "unreadable"
    if len(raw) > limit:
        return None, "too-large"  # grew after the size check
    return raw.decode("utf-8", errors="replace"), None


def safe_read(root: Path, rel: str) -> str | None:
    return read_bounded(root, rel)[0]


# Directory-fd traversal (openat-style) is used where the platform supports it. Every
# path component is opened relative to the already-open parent with O_NOFOLLOW, so a
# directory swapped for a symlink mid-run cannot redirect a write outside the root.
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
HAS_DIR_FD = bool(
    _O_NOFOLLOW and _O_DIRECTORY
    and os.open in os.supports_dir_fd
    and os.mkdir in os.supports_dir_fd
    and os.unlink in os.supports_dir_fd
    and os.stat in os.supports_dir_fd
)
_SYMLINK_ERRNOS = {errno.ELOOP, getattr(errno, "EMLINK", errno.ELOOP)}  # FreeBSD reports EMLINK


def _split_relative(rel: str) -> list[str] | None:
    """Lexically validate a project-relative path. Rejects absolute paths, drives, '..', '.', empty parts."""
    if not rel or "\x00" in rel or "\\" in rel:
        return None
    pure = PurePosixPath(rel)
    if pure.is_absolute() or PureWindowsPath(rel).drive:
        return None
    parts = rel.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    return parts


def safe_create(root: Path, rel: str, contents: str) -> str:
    """Create `root/rel` with `contents` only if nothing exists there. Never overwrites,
    never follows a symlink, never writes outside `root`. Returns a status string."""
    parts = _split_relative(rel)
    if parts is None:
        return "REFUSED: outside project"
    data = contents.encode("utf-8")
    if HAS_DIR_FD:
        return _create_dir_fd(root, parts, data)
    return _create_path_walk(root, parts, data)


def _create_dir_fd(root: Path, parts: list[str], data: bytes) -> str:
    dir_flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    opened: list[int] = []
    try:
        try:
            current = os.open(root, dir_flags)
        except OSError as exc:
            if exc.errno in _SYMLINK_ERRNOS or (exc.errno == errno.ENOTDIR and os.path.islink(root)):
                return "REFUSED: symlinked directory"
            return f"ERROR: unable to open project root ({exc.strerror})"
        opened.append(current)
        for part in parts[:-1]:
            for attempt in (1, 2):
                try:
                    current = os.open(part, dir_flags, dir_fd=current)
                    break
                except FileNotFoundError:
                    if attempt == 2:
                        return "ERROR: unable to create directory (it vanished during creation)"
                    try:
                        os.mkdir(part, 0o755, dir_fd=current)
                    except FileExistsError:
                        pass  # created concurrently; the retry opens it with O_NOFOLLOW
                    except OSError as exc:
                        return f"ERROR: unable to create directory ({exc.strerror})"
                except OSError as exc:
                    if exc.errno in _SYMLINK_ERRNOS or (exc.errno == errno.ENOTDIR and _is_symlink_at(current, part)):
                        return "REFUSED: symlinked directory"  # macOS reports ENOTDIR for O_DIRECTORY|O_NOFOLLOW on a link
                    if exc.errno == errno.ENOTDIR:
                        return "REFUSED: path parent is not a directory"
                    return f"ERROR: unable to open directory ({exc.strerror})"
            opened.append(current)
        return _create_leaf(current, parts[-1], data)
    finally:
        for fd in opened:
            os.close(fd)


def _is_symlink_at(dir_fd: int, name: str) -> bool:
    """Used only to choose the refusal message after an open was already refused."""
    try:
        return stat.S_ISLNK(os.stat(name, dir_fd=dir_fd, follow_symlinks=False).st_mode)
    except OSError:
        return False


def _create_leaf(parent_fd: int, name: str, data: bytes) -> str:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC
    try:
        fd = os.open(name, flags, 0o644, dir_fd=parent_fd)
    except FileExistsError:
        return _describe_existing(parent_fd, name, data)
    except OSError as exc:
        if exc.errno in _SYMLINK_ERRNOS:
            return "REFUSED: existing symlink"
        return f"ERROR: {exc.strerror}"
    try:
        _write_all(fd, data)
    except OSError as exc:
        # Remove only the file this call just created, and only if it is still that file.
        try:
            created = os.fstat(fd)
            now = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (now.st_dev, now.st_ino) == (created.st_dev, created.st_ino):
                os.unlink(name, dir_fd=parent_fd)
        except OSError:
            pass
        return f"ERROR: write failed ({exc.strerror}); partial file removed"
    finally:
        os.close(fd)
    return "CREATED"


def _describe_existing(parent_fd: int, name: str, data: bytes) -> str:
    """Classify an existing leaf without following symlinks or blocking on FIFOs."""
    try:
        fd = os.open(name, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK | _O_CLOEXEC, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in _SYMLINK_ERRNOS:
            return "REFUSED: existing symlink"
        return "PRESERVED (existing file differs; never overwritten)"
    try:
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode) and info.st_size == len(data) and _read_exact(fd, len(data)) == data:
            return "UNCHANGED (identical existing file)"
    except OSError:
        pass
    finally:
        os.close(fd)
    return "PRESERVED (existing file differs; never overwritten)"


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def _read_exact(fd: int, size: int) -> bytes:
    chunks, remaining = [], size + 1  # one extra byte detects growth
    while remaining:
        chunk = os.read(fd, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _create_path_walk(root: Path, parts: list[str], data: bytes) -> str:
    """Fallback for platforms without dir_fd support (notably Windows). Checks each
    ancestor, then creates the leaf exclusively. Not race-free: see docs/SAFETY.md."""
    path = root.joinpath(*parts)
    node = root
    for part in parts[:-1]:
        node = node / part
        if node.is_symlink():
            return "REFUSED: symlinked directory"
        if node.exists() and not node.is_dir():
            return "REFUSED: path parent is not a directory"
        if not node.exists():
            try:
                node.mkdir()
            except FileExistsError:
                if node.is_symlink() or not node.is_dir():
                    return "REFUSED: symlinked directory"
            except OSError as exc:
                return f"ERROR: unable to create directory ({exc.strerror})"
    if path.is_symlink():
        return "REFUSED: existing symlink"
    if path.exists():
        if is_local_regular_file(root, path):
            try:
                if path.read_bytes() == data:
                    return "UNCHANGED (identical existing file)"
            except OSError:
                pass
        return "PRESERVED (existing file differs; never overwritten)"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError:
        return "PRESERVED (file appeared; never overwritten)"
    except OSError as exc:
        return f"ERROR: {exc.strerror}"
    try:
        _write_all(fd, data)
    except OSError as exc:
        return f"ERROR: write failed ({exc.strerror})"
    finally:
        os.close(fd)
    return "CREATED"
