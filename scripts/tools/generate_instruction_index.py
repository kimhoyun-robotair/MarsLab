"""Regenerate Instruction/INDEX.md from the current Instruction/marslab/ tree.

Phase A-3 of the Instruction-wiki plan. Safe to re-run any time — it fully
overwrites INDEX.md using current frontmatter (`loc`, `status`, `source`).

Output sections:
1. Progress bar (draft/reviewed/needs_refactor counts)
2. Per-module table: file, LOC, status, source-docstring role, Isaac-Sim hit
3. Quick filters: files that touch Isaac Sim / ROS2
4. Glossary links
"""

from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "marslab"
WIKI_ROOT = REPO_ROOT / "Instruction" / "marslab"
INDEX_PATH = REPO_ROOT / "Instruction" / "INDEX.md"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
FIELD_RE = re.compile(r"^(\w+):\s*(.*?)\s*$", re.MULTILINE)


def read_frontmatter(md: Path) -> dict[str, str]:
    try:
        txt = md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    m = FRONTMATTER_RE.search(txt)
    if not m:
        return {}
    return {k: v.strip('"') for k, v in FIELD_RE.findall(m.group(1))}


def source_role_and_flags(py: Path) -> tuple[str, bool, bool]:
    """Return (first-line docstring, touches_isaac, touches_ros2)."""
    try:
        src = py.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "", False, False

    role = ""
    try:
        tree = ast.parse(src)
        doc = ast.get_docstring(tree)
        if doc:
            for line in doc.splitlines():
                line = line.strip()
                if line:
                    role = line
                    break
    except SyntaxError:
        pass

    touches_isaac = bool(re.search(r"\b(from|import)\s+(isaacsim|omni|pxr|carb)\b", src))
    touches_ros2 = bool(re.search(r"\b(from|import)\s+(rclpy|tf2_ros|\w+_msgs)\b", src))
    return role, touches_isaac, touches_ros2


def progress_bar(counts: dict[str, int], width: int = 30) -> str:
    total = sum(counts.values()) or 1
    filled_r = int(width * counts.get("reviewed", 0) / total)
    filled_n = int(width * counts.get("needs_refactor", 0) / total)
    filled_d = width - filled_r - filled_n
    bar = "█" * filled_r + "▒" * filled_n + "·" * filled_d
    return (
        f"`{bar}` "
        f"reviewed {counts.get('reviewed', 0)} / "
        f"needs_refactor {counts.get('needs_refactor', 0)} / "
        f"draft {counts.get('draft', 0)} "
        f"(total {total})"
    )


def main() -> int:
    # Group by module directory (first-level under marslab/)
    module_files: dict[str, list[Path]] = defaultdict(list)
    for py in sorted(SRC_ROOT.rglob("*.py")):
        rel = py.relative_to(REPO_ROOT)  # marslab/config/schema.py
        # module = first path component under marslab/
        parts = rel.parts
        if len(parts) == 2:
            module = "(root)"
        else:
            module = parts[1]
        module_files[module].append(py)

    status_counts: dict[str, int] = defaultdict(int)
    isaac_hits: list[tuple[str, str]] = []  # (rel_py, role)
    ros2_hits: list[tuple[str, str]] = []

    lines: list[str] = []
    lines.append("---")
    lines.append("title: MarsLab Instruction Wiki — INDEX")
    lines.append("type: meta")
    lines.append("generated_by: scripts/tools/generate_instruction_index.py")
    lines.append("---")
    lines.append("")
    lines.append("# MarsLab Instruction Wiki — INDEX")
    lines.append("")
    lines.append(
        "> **English summary (1 paragraph):** Auto-generated navigation for the "
        "MarsLab Instruction wiki. Each row mirrors one source file under `marslab/` "
        "and links to its twin `.md`. Re-run `scripts/tools/generate_instruction_index.py` "
        "after adding/removing source files or flipping a `.md` status to reviewed."
    )
    lines.append("")
    lines.append("## 진행률")
    lines.append("")
    lines.append("_(정확한 값은 아래 테이블에서 집계됨)_")
    lines.append("")
    progress_placeholder_idx = len(lines)
    lines.append("PLACEHOLDER_PROGRESS")
    lines.append("")

    # Per-module tables
    lines.append("## 모듈별 파일")
    lines.append("")

    for module in sorted(module_files.keys()):
        files = module_files[module]
        if module == "(root)":
            header = "### marslab/ (root)"
        else:
            header = f"### marslab/{module}/"
        lines.append(header)
        lines.append("")
        lines.append("| 파일 | LOC | status | 역할 | Isaac | ROS2 |")
        lines.append("|-----|-----|--------|------|-------|------|")

        for py in files:
            rel = py.relative_to(REPO_ROOT).as_posix()
            md_path = WIKI_ROOT / py.relative_to(SRC_ROOT).with_suffix(".md")
            fm = read_frontmatter(md_path)
            status = fm.get("status", "missing")
            status_counts[status] += 1
            loc = fm.get("loc", "?")
            role, isaac, ros2 = source_role_and_flags(py)
            role = role[:80] + ("…" if len(role) > 80 else "")
            if not role:
                role = "_(docstring 없음)_"
            md_link = f"[[Instruction/{py.relative_to(REPO_ROOT).with_suffix('').as_posix()}]]"
            isaac_mark = "✅" if isaac else ""
            ros2_mark = "✅" if ros2 else ""
            lines.append(
                f"| `{rel}` → {md_link} | {loc} | {status} | {role} | {isaac_mark} | {ros2_mark} |"
            )

            if isaac:
                isaac_hits.append((rel, role))
            if ros2:
                ros2_hits.append((rel, role))

        lines.append("")

    # Quick filters
    lines.append("## 빠른 필터")
    lines.append("")
    lines.append("### Isaac Sim / Omniverse / pxr 를 터치하는 파일")
    lines.append("")
    if isaac_hits:
        for rel, role in isaac_hits:
            lines.append(f"- `{rel}` — {role or '(docstring 없음)'}")
    else:
        lines.append("- (없음)")
    lines.append("")
    lines.append("### ROS2 (rclpy / tf2_ros / *_msgs) 를 터치하는 파일")
    lines.append("")
    if ros2_hits:
        for rel, role in ros2_hits:
            lines.append(f"- `{rel}` — {role or '(docstring 없음)'}")
    else:
        lines.append("- (없음)")
    lines.append("")

    # Glossary
    lines.append("## 글로서리")
    lines.append("")
    for name in sorted((REPO_ROOT / "Instruction" / "_glossary").glob("*.md")):
        stem = name.stem
        lines.append(f"- [[Instruction/_glossary/{stem}]]")
    lines.append("")

    lines.append("## 다음 단계")
    lines.append("")
    lines.append("- Phase A-4: `scripts/check_instruction_sync.py` (동형성 검증)")
    lines.append("- Phase B: 파일별 워크스루 — `marslab/utils/` 부터 시작 권장")
    lines.append(
        "- `.md` 프리필을 다시 돌리려면: `python3 scripts/tools/generate_instruction_skeleton.py`"
    )
    lines.append("")

    # Fill in the progress bar now that counts are known
    lines[progress_placeholder_idx] = progress_bar(status_counts)

    INDEX_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] wrote {INDEX_PATH.relative_to(REPO_ROOT)}")
    print(f"       counts: {dict(status_counts)}")
    print(f"       isaac-touching files: {len(isaac_hits)}")
    print(f"       ros2-touching files : {len(ros2_hits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
