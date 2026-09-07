"""Small, local-only input boundary for user-supplied exports."""
from pathlib import Path, PureWindowsPath
import re
import stat

MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_MANIFEST_BYTES = 256 * 1024
MAX_ROWS = 100_000
MAX_TOPICS = 50
MAX_TOTAL_BYTES = 50 * 1024 * 1024


def read_local_text(path, suffix, max_bytes):
    raw = str(path)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw) or raw.startswith(("\\\\", "//")):
        raise ValueError("Only local files are supported; URLs and network shares are not allowed.")
    path = Path(path)
    if path.suffix.lower() != suffix:
        raise ValueError(f"Expected an uncompressed {suffix} file.")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Input must be a regular file.")
    if info.st_size > max_bytes:
        raise ValueError("Input file exceeds the size limit.")
    with path.open("rb") as stream:
        contents = stream.read(max_bytes + 1)
    if len(contents) > max_bytes:
        raise ValueError("Input file exceeds the size limit.")
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeError:
        raise ValueError("Input must be UTF-8 text.") from None
    if "\x00" in text:
        raise ValueError("Binary content is not supported.")
    return text


def manifest_file(root, value):
    """An export named by a manifest must stay inside the manifest directory."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Export paths must be nonempty relative file names.")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value) or PureWindowsPath(value).drive or value.startswith(("/", "\\")):
        raise ValueError("Export paths must be relative to the manifest directory.")
    root = Path(root).resolve()
    resolved = (root / value.replace("\\", "/")).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Export path escapes the manifest directory.")
    return resolved
