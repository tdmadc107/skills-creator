#!/usr/bin/env python3
"""Register every skill of the skills folders in the repository's instruction file (AGENTS.md or CLAUDE.md).

The registration rule is owned by ../references/skill-format.md#registration; this script applies it: it picks the
instruction files, writes one generated block listing every skill, replaces that block when it exists and leaves
the rest of each file untouched. With --check it writes nothing and fails when a block is missing or out of date.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (BLOCK, INSTRUCTION_FILES, SkillError, emit, registration_block, skills_dirs,  # noqa: E402
                     registration_targets, resolve, shown)

NEW_FILE_HEADING = "# Agent instructions"


def updated(current: str | None, block: str) -> str:
    """The text of an instruction file once it carries the block, in the line endings the file already uses."""

    if current is None:
        return f"{NEW_FILE_HEADING}\n\n{block}\n"
    newline = "\r\n" if "\r\n" in current else "\n"
    block = block.replace("\n", newline)
    if BLOCK.search(current):
        return BLOCK.sub(lambda _: block, current, count=1)
    return current.rstrip("\r\n") + newline * 2 + block + newline if current.strip() else block + newline


def read(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def register(root: Path, named_dirs: list[str] | None, create: str | None, check: bool) -> dict[str, object]:
    skipped: list[str] = []
    block = registration_block(root, [resolve(name, root) for name in skills_dirs(root, named_dirs)], skipped)
    files, stale = [], []
    for target in registration_targets(root, create):
        current = read(target)
        text = updated(current, block)
        state = "created" if current is None else ("unchanged" if text == current else "updated")
        files.append({"path": shown(target, root), "state": state})
        if state == "unchanged":
            continue
        if check:
            stale.append(f"{shown(target, root)} does not list the skills as they are now; run the registration without --check")
        else:
            with target.open("w", encoding="utf-8", newline="") as handle:
                handle.write(text)
    if stale:
        return {"passed": False, "errors": stale}
    return {"passed": True, "files": files, **({"skipped": skipped} if skipped else {})}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skills-dir", action="append", help="a skills folder, relative to the root; repeatable; default: the skills folder of every provider the repository uses")
    parser.add_argument("--create", choices=INSTRUCTION_FILES,
                        help="the file to create when the root has none of them; default: CLAUDE.md when Claude Code is the only provider in use, otherwise AGENTS.md")
    parser.add_argument("--check", action="store_true", help="write nothing; fail when a block is missing or out of date")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="root of the repository (default: the current directory)")
    args = parser.parse_args()
    try:
        result = register(args.root.resolve(), args.skills_dir, args.create, args.check)
    except (SkillError, OSError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
