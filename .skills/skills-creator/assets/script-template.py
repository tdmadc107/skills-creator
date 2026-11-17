#!/usr/bin/env python3
"""Create one {{artifact}} file from the {{name}} skill's template, with the computed values filled in.

The layout, naming and location rules are owned by ../references/{{artifact}}-format.md; this script fills only
what a tool can compute (the file name and the timestamp) and leaves every <...> placeholder to the agent.
It never overwrites a file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL / "assets" / "{{artifact}}-template.md"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
# The default output directory of the format reference, relative to the repository root.
DEFAULT_OUT_DIR = "."


class InputError(Exception):
    """An argument that breaks a rule of the format reference."""


def shown(path: Path, root: Path) -> str:
    """A path as the output names it: relative to the repository root when inside it, otherwise absolute."""

    return path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()


def create(root: Path, slug: str, out_dir: str) -> dict[str, str]:
    if not SLUG.fullmatch(slug):
        raise InputError("--slug must be ASCII kebab-case")
    base = (Path(out_dir) if Path(out_dir).is_absolute() else root / out_dir).resolve()
    now = datetime.now().astimezone()
    target = base / f"{slug}-{now:%Y%m%d-%H%M%S}.md"
    if target.exists():
        raise InputError(f"{shown(target, root)} already exists")
    text = TEMPLATE.read_text(encoding="utf-8").replace("{{created_at}}", now.isoformat(timespec="seconds"))
    base.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")
    return {"path": shown(target, root)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", required=True, help="ASCII kebab-case slug of the file")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="directory that receives the file, relative to the root or absolute")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root (default: the current directory)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = {"passed": True, **create(args.root.resolve(), args.slug, args.out_dir)}
    except (InputError, OSError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
