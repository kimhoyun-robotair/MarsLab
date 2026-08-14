from __future__ import annotations

from pathlib import Path

from marslab.validation.models import Diagnostic, Severity, ValidationReport


def _diagnostic(code: str, message: str, path: Path) -> Diagnostic:
    return Diagnostic(code=code, severity=Severity.ERROR, message=message, path=str(path))


def _has_unrecognized_usda_root_token(source: bytes) -> bool:
    try:
        lines = source.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return True
    for line in lines[1:]:
        content = line.lstrip()
        if not content or content.startswith("#"):
            continue
        if content.startswith("("):
            return False
        root_token = content.split(maxsplit=1)[0]
        return root_token not in {"class", "def", "over"}
    return False


def validate_rover_file(path: Path) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    try:
        source = path.read_bytes()
    except OSError as exc:
        diagnostics.append(_diagnostic("rover.file.missing", f"unreadable Rover USD: {exc}", path))
    else:
        header = source[:8]
        if not (header.startswith(b"PXR-USDC") or header.startswith(b"#usda")):
            diagnostics.append(
                _diagnostic("rover.file.corrupt", "Rover USD has no recognized USD header", path)
            )
        elif header.startswith(b"#usda") and _has_unrecognized_usda_root_token(source):
            diagnostics.append(
                _diagnostic("rover.file.corrupt", "Rover USDA has an invalid root token", path)
            )
    return ValidationReport(kind="rover-file", path=str(path), diagnostics=tuple(diagnostics))


__all__ = ["validate_rover_file"]
