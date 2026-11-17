"""Shared code of the skills-creator scripts: reading a skill, its sections, the names and the registration block.

The rules these helpers apply are owned by ../references/skill-format.md; this module only reads and computes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SEMVER = re.compile(r"\d+\.\d+\.\d+")
NAME_LIMIT = 64
DESCRIPTION_LIMIT = 1024
SKILLS_DIR = ".skills"
# The instruction files a skill is registered in, in the order they are looked for.
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
RESOURCE_FOLDERS = ("assets", "references", "scripts")
BLOCK_START = "<!-- skills:start -->"
BLOCK_END = "<!-- skills:end -->"
BLOCK = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
FENCE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
HEADING = re.compile(r"(?m)^(#{1,6}) (.+?)\s*$")
STEP = re.compile(r"(?m)^(\d+)\. (.*)$")
# The tool that opens and records every run of a skill, and the folder of the skills directory that keeps the records.
RECORD_TOOL = "run_record.py"
RECORDS = ".records"


class SkillError(Exception):
    """A rule of the skill format that the input breaks, worded for the person who fixes it."""


def emit(result: dict[str, Any]) -> int:
    """Print the result as JSON and return the exit code that matches it."""

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def shown(path: Path, root: Path) -> str:
    """A path as the output names it: relative to the repository root when inside it, otherwise absolute."""

    return path.relative_to(root).as_posix() if path.is_relative_to(root) else path.as_posix()


def resolve(value: str, root: Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def parse_scalar(raw: str, where: str) -> Any:
    value = raw.strip()
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except ValueError as exc:
            raise SkillError(f"{where}: the double-quoted value is not closed or escapes a character wrongly") from exc
        if not isinstance(parsed, str):
            raise SkillError(f"{where}: the value must be one quoted string")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise SkillError(f"{where}: the single-quoted value is not closed")
        return value[1:-1].replace("''", "'")
    if value.startswith("["):
        if not value.endswith("]"):
            raise SkillError(f"{where}: the inline list is not closed")
        return [parse_scalar(item, where) for item in value[1:-1].split(",") if item.strip()]
    if ": " in value or " #" in value or value.endswith(":"):
        raise SkillError(f"{where}: quote the value, because it contains ': ' or ' #'")
    return value


def parse_frontmatter(text: str, where: str) -> tuple[dict[str, Any], str]:
    """Read the YAML subset a skill uses: `key: value` lines and one level of nested keys.

    Returns the fields and the body below the frontmatter.
    """

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise SkillError(f"{where}: the file must start with a frontmatter block opened by ---")
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        raise SkillError(f"{where}: the frontmatter block is not closed by ---") from None
    meta: dict[str, Any] = {}
    parent: dict[str, Any] | None = None
    for number, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line.startswith((" ", "\t"))
        key, separator, raw = line.strip().partition(":")
        spot = f"{where}:{number}"
        if not separator or not key or (raw and not raw.startswith(" ")):
            raise SkillError(f"{spot}: expected `key: value`")
        if indented:
            if parent is None:
                raise SkillError(f"{spot}: an indented key needs a parent key above it")
            parent[key] = parse_scalar(raw, spot)
        elif raw.strip():
            meta[key], parent = parse_scalar(raw, spot), None
        else:
            parent = meta[key] = {}
    return meta, "\n".join(lines[end + 1:])


def read_skill(skill: Path) -> tuple[dict[str, Any], str]:
    entry = skill / "SKILL.md"
    if not entry.is_file():
        raise SkillError(f"{skill.name}: SKILL.md is missing")
    return parse_frontmatter(entry.read_text(encoding="utf-8"), f"{skill.name}/SKILL.md")


def without_fences(text: str) -> str:
    return FENCE.sub("", text)


def sections(body: str) -> tuple[list[str], str, dict[str, str]]:
    """The level-one headings, the text between the title and the first section, and each level-two section."""

    plain = without_fences(body)
    titles = [heading for marks, heading in HEADING.findall(plain) if marks == "#"]
    parts = re.split(r"(?m)^## (.+?)\s*$", plain)
    opening = HEADING.sub("", parts[0]).strip()
    return titles, opening, {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def procedure_steps(body: str) -> list[tuple[int, str]]:
    """The numbered steps of the Procedure section: number and the text of the step's first line."""

    return [(int(number), text) for number, text in STEP.findall(sections(body)[2].get("Procedure", ""))]


def skill_folders(skills_dir: Path) -> list[Path]:
    """Every folder of the skills directory that holds a SKILL.md, by name."""

    if not skills_dir.is_dir():
        return []
    return sorted(folder for folder in skills_dir.iterdir() if (folder / "SKILL.md").is_file())


def registration_block(root: Path, skills_dir: Path) -> str:
    """The block an instruction file carries: one row per skill of the skills directory."""

    rows = []
    for folder in skill_folders(skills_dir):
        meta, _ = read_skill(folder)
        name, description = meta.get("name"), meta.get("description")
        if not isinstance(name, str) or not isinstance(description, str) or not name or not description:
            raise SkillError(f"{folder.name}/SKILL.md: name and description are required to register the skill")
        cell = " ".join(description.split()).replace("|", "\\|")
        rows.append(f"| [`{name}`]({shown(folder / 'SKILL.md', root)}) | {cell} |")
    if not rows:
        raise SkillError(f"{shown(skills_dir, root)} holds no skill to register")
    folder_name = shown(skills_dir, root)
    return "\n".join([
        BLOCK_START,
        "## Skills",
        "",
        f"This block is generated from the `SKILL.md` files in `{folder_name}/`: change those files, then register the skills again; do not edit it by hand.",
        "",
        "When a request matches the description of a skill below, read that skill's `SKILL.md` in full and follow it; relative paths in that file resolve from its own folder.",
        "When no skill matches, work without one.",
        "",
        "| Skill | Description |",
        "| --- | --- |",
        *rows,
        BLOCK_END,
    ])


def registration_targets(root: Path, create: str = INSTRUCTION_FILES[0]) -> list[Path]:
    """The instruction files that carry the block, per the registration rule of the skill format.

    `create` names the file to create when the root has none of them; it changes nothing once one exists.
    """

    agents, claude = (root / name for name in INSTRUCTION_FILES)
    targets = [agents] if agents.is_file() else []
    if claude.is_file() and not (targets and "AGENTS.md" in claude.read_text(encoding="utf-8")):
        targets.append(claude)
    return targets or [root / create]
