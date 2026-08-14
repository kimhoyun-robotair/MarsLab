import hashlib
from pathlib import Path, PurePosixPath


def find_repo_root(manifest_path: Path) -> Path | None:
    for candidate in (manifest_path.parent, *manifest_path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def safe_path(root: Path, relative: str) -> Path | None:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        return None
    candidate = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def safe_archive_member(name: str) -> bool:
    member = PurePosixPath(name)
    return not member.is_absolute() and ".." not in member.parts and "\\" not in name


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = ["find_repo_root", "safe_archive_member", "safe_path", "sha256"]
