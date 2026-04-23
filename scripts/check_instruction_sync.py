"""Verify `marslab/**/*.py` ↔ `Instruction/marslab/**/*.md` tree isomorphism.

Phase A-4 of the Instruction-wiki plan. Part of MarsLab's "Source↔Wiki Parity"
invariant: whenever the source tree changes (add/rename/move/split/merge/
delete), the Instruction/ wiki tree must change in the same diff.

Checks performed:
  1. Every `marslab/**/*.py` has a twin `Instruction/marslab/**/*.md`.
  2. Every `.md` under `Instruction/marslab/` has a matching `.py` source.
  3. Each `.md` frontmatter `source:` path exists on disk.
  4. (With --staged) Any staged `.py` has its twin `.md` also staged.

Exit codes:
  0  — all good
  1  — drift detected, details printed
  2  — tool error (e.g. git not available and --staged was requested)

Usage:
  python3 scripts/check_instruction_sync.py
  python3 scripts/check_instruction_sync.py --staged   # pre-commit mode
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "marslab"
WIKI_ROOT = REPO_ROOT / "Instruction" / "marslab"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
SOURCE_FIELD_RE = re.compile(r"^source:\s*(.+?)\s*$", re.MULTILINE)


def py_to_md(py: Path) -> Path:
    """marslab/config/schema.py -> Instruction/marslab/config/schema.md"""
    return WIKI_ROOT / py.relative_to(SRC_ROOT).with_suffix(".md")


def md_to_py(md: Path) -> Path:
    """Instruction/marslab/config/schema.md -> marslab/config/schema.py"""
    return SRC_ROOT / md.relative_to(WIKI_ROOT).with_suffix(".py")


def read_source_field(md: Path) -> str | None:
    try:
        txt = md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm = FRONTMATTER_RE.search(txt)
    if not fm:
        return None
    m = SOURCE_FIELD_RE.search(fm.group(1))
    return m.group(1) if m else None


def check_tree_isomorphism() -> list[str]:
    errors: list[str] = []

    py_files = sorted(SRC_ROOT.rglob("*.py"))
    md_files = sorted(WIKI_ROOT.rglob("*.md"))

    expected_md = {py_to_md(p).resolve() for p in py_files}
    actual_md = {p.resolve() for p in md_files}

    missing_md = sorted(expected_md - actual_md)
    orphan_md = sorted(actual_md - expected_md)

    for md in missing_md:
        try:
            disp = md.relative_to(REPO_ROOT)
        except ValueError:
            disp = md
        errors.append(f"[missing-md] no twin for .py → expected {disp}")

    for md in orphan_md:
        try:
            disp = md.relative_to(REPO_ROOT)
        except ValueError:
            disp = md
        errors.append(f"[orphan-md] .md exists but no matching .py → {disp}")

    return errors


def check_frontmatter_sources() -> list[str]:
    errors: list[str] = []
    for md in sorted(WIKI_ROOT.rglob("*.md")):
        src = read_source_field(md)
        if src is None:
            errors.append(
                f"[no-source] missing `source:` in frontmatter → " f"{md.relative_to(REPO_ROOT)}"
            )
            continue
        src_path = (REPO_ROOT / src).resolve()
        if not src_path.exists():
            errors.append(
                f"[dead-source] {md.relative_to(REPO_ROOT)} points at "
                f"non-existent `source: {src}`"
            )
    return errors


def check_staged_pairs() -> list[str]:
    """If a .py under marslab/ is staged, its twin .md must also be staged."""
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=REPO_ROOT,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return [f"[git-error] {exc}"]

    staged = {Path(line) for line in out.splitlines() if line.strip()}
    errors: list[str] = []

    for py_rel in sorted(p for p in staged if p.parts[:1] == ("marslab",) and p.suffix == ".py"):
        md_rel = Path("Instruction") / Path("marslab") / py_rel.relative_to("marslab")
        md_rel = md_rel.with_suffix(".md")
        if md_rel not in staged:
            errors.append(f"[unpaired] {py_rel} staged but {md_rel} not staged")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--staged",
        action="store_true",
        help="Also check that staged .py files have their .md staged (pre-commit mode)",
    )
    args = ap.parse_args()

    all_errors: list[str] = []
    all_errors += check_tree_isomorphism()
    all_errors += check_frontmatter_sources()
    if args.staged:
        all_errors += check_staged_pairs()

    if not all_errors:
        py_count = sum(1 for _ in SRC_ROOT.rglob("*.py"))
        md_count = sum(1 for _ in WIKI_ROOT.rglob("*.md"))
        print(f"[ok] {py_count} .py ↔ {md_count} .md in sync")
        return 0

    for err in all_errors:
        print(err)
    print(f"\n[fail] {len(all_errors)} drift issue(s)")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
