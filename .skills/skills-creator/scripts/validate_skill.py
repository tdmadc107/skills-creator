#!/usr/bin/env python3
"""Check the structure of a skill against the skill format: frontmatter, sections, resources, links, registration.

The rules are owned by ../references/skill-format.md; this script only reports where a skill departs from them.
It checks structure, never the quality of the wording: that is re-read per ../references/writing-rules.md.
--path names one skill folder, or a skills directory to check every skill in it.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (DESCRIPTION_LIMIT, HEADING, INSTRUCTION_FILES, NAME_LIMIT, recorded_steps, RECORD_TOOL, RESOURCE_FOLDERS, SEMVER, SLUG, SkillError, emit,  # noqa: E402
                     procedure_steps, read_skill, resolve, sections, shown, skill_folders, without_fences)
from register_skills import register  # noqa: E402

CODE_SPAN = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
PLACEHOLDER = re.compile(r"\{\{[^{}\n]*\}\}|<(?!!--)(?![a-z][a-z0-9+.-]*:)[^<>\n]+>")
SECTIONS = ("When to use", "Resources", "Procedure")


def anchors(text: str) -> set[str]:
    """GitHub heading anchors: lowercase, punctuation dropped, spaces turned into hyphens."""

    return {re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
            for _, heading in HEADING.findall(without_fences(text))}


def check_frontmatter(skill: Path, root: Path, meta: dict) -> list[str]:
    errors = []
    name, description, metadata = meta.get("name"), meta.get("description"), meta.get("metadata")
    if not isinstance(name, str) or not SLUG.fullmatch(name) or len(name) > NAME_LIMIT:
        errors.append(f"name must be ASCII kebab-case, at most {NAME_LIMIT} characters")
    elif name != skill.name:
        errors.append(f"name `{name}` must equal the folder name `{skill.name}`")
    if not isinstance(description, str) or not description.strip():
        errors.append("description is required")
    else:
        if len(description) > DESCRIPTION_LIMIT:
            errors.append(f"description has {len(description)} characters; the limit is {DESCRIPTION_LIMIT}")
        if PLACEHOLDER.search(description):
            errors.append("description still holds a placeholder")
    if not isinstance(metadata, dict):
        return errors + ["metadata with id, kind and version is required"]
    if metadata.get("id") != shown(skill, root):
        errors.append(f"metadata.id must be the path of the skill folder from the repository root: {shown(skill, root)}")
    if metadata.get("kind") != "skill":
        errors.append("metadata.kind must be `skill`")
    if not SEMVER.fullmatch(str(metadata.get("version", ""))):
        errors.append("metadata.version must have the form <major>.<minor>.<patch>")
    return errors


def check_body(body: str) -> list[str]:
    errors = []
    titles, opening, found = sections(body)
    if len(titles) != 1:
        errors.append(f"the body must have exactly one level-one title; it has {len(titles)}")
    if not opening:
        errors.append("the paragraph that says what the skill carries out and what it owns is missing below the title")
    if list(found) != list(SECTIONS):
        errors.append(f"the level-two sections must be, in this order: {', '.join(SECTIONS)}; found: {', '.join(found) or 'none'}")
    if "When to use" in found and not re.search(r"(?m)^- \S", found["When to use"]):
        errors.append("When to use must list when the skill applies and when it does not")
    if "Procedure" in found:
        steps = procedure_steps(body)
        if [number for number, _ in steps] != list(range(1, len(steps) + 1)) or len(steps) < 2:
            errors.append("Procedure must be a list of at least two steps numbered from 1 without gaps")
        unnamed = [str(number) for number, text in steps if not re.match(r"\*\*[^*]+\*\*", text)]
        if unnamed:
            errors.append(f"each step starts with its name in bold; missing at step {', '.join(unnamed)}")
        try:
            recorded_steps(body, "Procedure")
        except SkillError as exc:
            errors.append(str(exc))
    left = PLACEHOLDER.findall(CODE_SPAN.sub("", without_fences(body)))
    if left:
        errors.append(f"SKILL.md still holds {len(left)} placeholder(s) outside code, the first one: {left[0]}")
    return errors


def resource_files(skill: Path) -> dict[str, list[Path]]:
    return {folder: sorted(path for path in (skill / folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
            for folder in RESOURCE_FOLDERS if (skill / folder).is_dir()}


def check_resources(skill: Path, resources: dict[str, list[Path]]) -> list[str]:
    errors = [f"{folder}/ is empty; remove the folder or add its resource" for folder, files in resources.items() if not files]
    errors += [f"{entry.name}/ is not a folder of the skill format; a skill holds only {', '.join(RESOURCE_FOLDERS)}"
               for entry in sorted(skill.iterdir()) if entry.is_dir() and entry.name not in (*RESOURCE_FOLDERS, "__pycache__")]
    text = without_fences((skill / "SKILL.md").read_text(encoding="utf-8"))
    linked = {(skill / target.partition("#")[0]).resolve() for target in LINK.findall(text) if not re.match(r"[a-z][a-z0-9+.-]*:", target)}
    if RECORD_TOOL not in {path.name for path in linked}:
        errors.append(f"the Resources table must link the record tool {RECORD_TOOL}: every run of a skill is opened and recorded with it")
    for files in resources.values():
        for path in files:
            # A file whose name starts with an underscore is shared code of the scripts, not a resource of its own.
            if not path.name.startswith("_") and path.resolve() not in linked:
                errors.append(f"{shown(path, skill)} has no row in the Resources table of SKILL.md")
    return errors


def check_links(skill: Path) -> list[str]:
    """Relative links and their anchors must resolve; templates in assets/ resolve from where their output is written, so they are left out."""

    errors = []
    for source in sorted(skill.rglob("*.md")):
        if "assets" in source.relative_to(skill).parts:
            continue
        text = without_fences(source.read_text(encoding="utf-8"))
        spans = [match.span() for match in CODE_SPAN.finditer(text)]
        for match in LINK.finditer(text):
            target = match.group(1)
            if re.match(r"[a-z][a-z0-9+.-]*:", target) or any(start <= match.start() and match.end() <= end for start, end in spans):
                continue
            file_part, _, anchor = target.partition("#")
            resolved = (source.parent / file_part).resolve() if file_part else source
            where = f"{shown(source, skill)}: link {target}"
            if not resolved.exists():
                errors.append(f"{where} names a file that does not exist")
            elif anchor and resolved.suffix == ".md" and anchor not in anchors(resolved.read_text(encoding="utf-8")):
                errors.append(f"{where} names a heading that does not exist")
    return errors


def check_scripts(skill: Path, resources: dict[str, list[Path]]) -> list[str]:
    errors = []
    for path in resources.get("scripts", []):
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
        except SyntaxError as exc:
            errors.append(f"{shown(path, skill)} does not parse: {exc.msg} at line {exc.lineno}")
            continue
        if not ast.get_docstring(tree):
            errors.append(f"{shown(path, skill)} needs a module docstring that says what it does and which file owns its rules")
    return errors


def check_skill(skill: Path, root: Path) -> list[str]:
    try:
        meta, body = read_skill(skill)
    except SkillError as exc:
        return [str(exc)]
    resources = resource_files(skill)
    errors = (check_frontmatter(skill, root, meta) + check_body(body) + check_resources(skill, resources)
              + check_links(skill) + check_scripts(skill, resources))
    return [f"{skill.name}: {error}" for error in errors]


def validate(root: Path, path: Path, skip_registration: bool) -> list[str]:
    if not path.is_dir():
        raise SkillError(f"{shown(path, root)} is not a directory")
    skills = [path] if (path / "SKILL.md").is_file() else skill_folders(path)
    if not skills:
        raise SkillError(f"{shown(path, root)} is neither a skill folder nor a directory of skills")
    errors = [error for skill in skills for error in check_skill(skill, root)]
    if not skip_registration:
        errors += register(root, str(skills[0].parent), INSTRUCTION_FILES[0], check=True).get("errors", [])
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--path", required=True, help="a skill folder, or a skills directory to check every skill in it; relative to the root or absolute")
    parser.add_argument("--skip-registration", action="store_true", help="do not check that the instruction file lists the skills")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="root of the repository (default: the current directory)")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        errors = validate(root, resolve(args.path, root), args.skip_registration)
        result = {"passed": not errors, "path": args.path, **({"errors": errors} if errors else {})}
    except (SkillError, OSError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
