"""Asset manifest filesystem and checksum boundary."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

import yaml
from pydantic import JsonValue, TypeAdapter

from marslab_scene.config.paths import resolve_manifest_file
from marslab_scene.errors import ArtifactManifestError, ContractValueError

_JSON_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)


def load_asset_yaml(path: Path) -> JsonValue:
    """Parse YAML into JSON-compatible input for a strict manifest model."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ArtifactManifestError(path=path, detail=str(error)) from error
    return _JSON_ADAPTER.validate_python(raw)


def validate_bundle_digests(root: Path, digests: dict[str, str]) -> str:
    """Validate every declared file and return the specified bundle digest."""
    bundle_hash = hashlib.sha256()
    for relative in sorted(digests):
        path = resolve_manifest_file(root, relative)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = digests[relative]
        if actual != expected:
            detail = f"digest mismatch for {relative}: expected {expected}, got {actual}"
            raise ContractValueError(detail)
        bundle_hash.update(relative.encode("utf-8"))
        bundle_hash.update(b"\0")
        bundle_hash.update(actual.encode("ascii"))
        bundle_hash.update(b"\n")
    return bundle_hash.hexdigest()


def require_digest_coverage(digests: dict[str, str], files: tuple[Path, ...]) -> None:
    """Require checksums for exactly the files named by the manifest."""
    declared = set(digests)
    required = {path.as_posix() for path in files}
    if declared != required:
        missing = sorted(required - declared)
        extra = sorted(declared - required)
        detail = f"digest inventory mismatch: missing={missing}, extra={extra}"
        raise ContractValueError(detail)
