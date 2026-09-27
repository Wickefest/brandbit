# Keeps user supplied file names inside a configured base directory.
# Blocks absolute paths and path traversal before reading or writing files.
from __future__ import annotations
from pathlib import Path


def _is_absolute_name(name: str) -> bool:
    if name.startswith(("/", "\\")):
        return True
    # Detect Windows drive letter paths.
    if len(name) >= 2 and name[1] == ":" and name[0].isalpha():
        return True
    return False


def sanitize_leaf_name(name: str) -> str:
    # Reject empty absolute separator and parent path names.
    raw = str(name).strip()
    if not raw:
        raise ValueError("empty path name")
    if _is_absolute_name(raw):
        raise ValueError("absolute paths are not allowed")
    if "/" in raw or "\\" in raw:
        raise ValueError("path separators are not allowed")
    if ".." in Path(raw).parts or raw == ".." or raw.startswith(".."):
        raise ValueError("path traversal is not allowed")
    return raw


def contained_path(base_dir: Path | str, name: str, *, suffix: str = "") -> Path:
    # Ensure the final path stays inside the base directory.
    base = Path(base_dir).expanduser().resolve()
    leaf = sanitize_leaf_name(name)
    if suffix and not leaf.endswith(suffix):
        leaf = f"{leaf}{suffix}"
    candidate = (base / leaf).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError("path escapes base directory")
    return candidate
