#!/usr/bin/env python3
"""Create a new skill from the skills-generator templates in every skills folder, with the computed values filled in.

The layout and naming rules are owned by ../references/skill-format.md; this script fills only what a tool can
compute (the name, the id, the resource file names, the paths of the skill and of the record tool) and leaves every <...> placeholder to
the agent that writes the skill. Each skills folder of the repository gets a copy, which runs the copy of
skills-generator in the same folder. It never overwrites a file: it writes nothing when one of the folders exists.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import NAME_LIMIT, SLUG, SkillError, emit, resolve, shown, skills_dirs  # noqa: E402

ASSETS = SKILL / "assets"


def plan(name: str, size: str, artifact: str | None) -> dict[str, str]:
    """The files of the new skill: path inside the skill folder -> template that fills it."""

    if size == "thin":
        return {"SKILL.md": "skill-thin-template.md"}
    snake = artifact.replace("-", "_")
    return {
        "SKILL.md": "skill-template.md",
        f"assets/{artifact}-template.md": "output-template.md",
        f"references/{artifact}-format.md": "format-template.md",
        f"scripts/new_{snake}.py": "script-template.py",
    }


def create(root: Path, named_dirs: list[str] | None, name: str, size: str, artifact: str | None) -> dict[str, object]:
    if not SLUG.fullmatch(name) or len(name) > NAME_LIMIT:
        raise SkillError(f"--name must be ASCII kebab-case, at most {NAME_LIMIT} characters")
    if size == "full" and not artifact:
        raise SkillError("--artifact is required with --size full: the kebab-case name of the output the skill produces")
    if size == "thin" and artifact:
        raise SkillError("--artifact applies only to --size full")
    if artifact and not SLUG.fullmatch(artifact):
        raise SkillError("--artifact must be ASCII kebab-case")
    if not SKILL.is_relative_to(root):
        # Every skill runs the record tool of a copy in the repository, so a path outside it would break for everyone else.
        raise SkillError(f"this skill's folder is outside {root.as_posix()}; install skills-generator into the repository, then run its copy")
    dirs = skills_dirs(root, named_dirs)
    # Check every folder before writing any, so one refusal leaves no partial copy.
    for skills_dir in dirs:
        folder = resolve(skills_dir, root) / name
        if folder.exists():
            raise SkillError(f"{shown(folder, root)} already exists; edit that skill, in every skills folder, instead of creating it")
        if not (resolve(skills_dir, root) / SKILL.name / "SKILL.md").is_file():
            raise SkillError(f"{skills_dir}/{SKILL.name} is missing; run `npx skills-generator` at the root of the repository to install it in every skills folder")
    paths, files = [], []
    for skills_dir in dirs:
        folder = resolve(skills_dir, root) / name
        path = shown(folder, root)
        creator = resolve(skills_dir, root) / SKILL.name
        values = {"{{name}}": name, "{{id}}": path, "{{skill_path}}": path, "{{creator_path}}": shown(creator, root),
                  "{{creator_rel}}": Path(os.path.relpath(creator, folder)).as_posix()}
        if artifact:
            values.update({"{{artifact}}": artifact, "{{artifact_snake}}": artifact.replace("-", "_")})
        for target, template in plan(name, size, artifact).items():
            text = (ASSETS / template).read_text(encoding="utf-8")
            for placeholder, value in values.items():
                text = text.replace(placeholder, value)
            destination = folder / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(text)
            files.append(f"{path}/{target}")
        paths.append(path)
    return {"path": paths[0], "paths": paths, "name": name, "size": size, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", required=True, help="ASCII kebab-case name of the skill; it becomes the folder name")
    parser.add_argument("--size", required=True, choices=("thin", "full"), help="thin: SKILL.md only; full: SKILL.md with assets/, references/ and scripts/")
    parser.add_argument("--artifact", help="with --size full: ASCII kebab-case name of the output the skill produces, used in the resource file names")
    parser.add_argument("--skills-dir", action="append", help="a skills folder, relative to the root; repeatable; default: the skills folder of every provider the repository uses")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="root of the repository that receives the skill (default: the current directory)")
    args = parser.parse_args()
    try:
        result = {"passed": True, **create(args.root.resolve(), args.skills_dir, args.name, args.size, args.artifact)}
    except (SkillError, OSError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
