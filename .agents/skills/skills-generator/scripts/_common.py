"""Shared code of the skills-generator scripts: reading a skill, its sections, the names and the registration block.

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
# The agent providers whose skills folder receives every skill, in the order their folders are listed.
# A provider is in use when one of its `detect` paths, or its skills folder, exists at the repository root.
# bin/skills-generator.mjs holds the same table for the installer, and a test keeps the two equal.
PROVIDERS = (
    {"id": "agents", "label": "Codex CLI, Antigravity and other agents that read .agents/", "skills": ".agents/skills", "detect": (".agents", ".codex", ".agent")},
    {"id": "claude", "label": "Claude Code", "skills": ".claude/skills", "detect": (".claude", "CLAUDE.md")},
    {"id": "cursor", "label": "Cursor", "skills": ".cursor/skills", "detect": (".cursor",)},
    {"id": "gemini", "label": "Gemini CLI", "skills": ".gemini/skills", "detect": (".gemini", "GEMINI.md")},
    {"id": "copilot", "label": "GitHub Copilot", "skills": ".github/skills", "detect": (".github/copilot-instructions.md", ".github/instructions")},
)
# The skills folder created when the repository uses no provider yet.
DEFAULT_SKILLS_DIR = ".agents/skills"
# The instruction files a skill is registered in, in the order they are looked for.
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md")
RESOURCE_FOLDERS = ("assets", "references", "scripts")
BLOCK_START = "<!-- skills:start -->"
BLOCK_END = "<!-- skills:end -->"
BLOCK = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END), re.S)
FENCE = re.compile(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
HEADING = re.compile(r"(?m)^(#{1,6}) (.+?)\s*$")
STEP = re.compile(r"(?m)^(\d+)\. (.*)$")
# The tool that opens and records every run of a skill, and the folder of each skills folder that keeps the records.
RECORD_TOOL = "run_record.py"
RECORDS = ".records"
# The two steps that end every procedure, in this order; a record covers every step before them.
CLOSING_STEPS = ("Evaluate and record", "Report")
STEP_NAME = re.compile(r"\*\*([^*]+?)\.?\*\*")


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


BLOCK_SCALAR = re.compile(r"[|>][+-]?")


def parse_frontmatter(text: str, where: str) -> tuple[dict[str, Any], str]:
    """Read the YAML subset a skill uses: `key: value` lines, one level of nested keys, and `>` or `|` block values.

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
    number = 1
    while number < end:
        line = lines[number]
        number += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indented = line.startswith((" ", "\t"))
        key, separator, raw = line.strip().partition(":")
        spot = f"{where}:{number}"
        if not separator or not key or (raw and not raw.startswith(" ")):
            raise SkillError(f"{spot}: expected `key: value`")
        if BLOCK_SCALAR.fullmatch(raw.strip()):
            # A block value: the more indented lines below, folded into one line by `>` or kept as lines by `|`.
            own = len(line) - len(line.lstrip())
            block = []
            while number < end and (not lines[number].strip() or len(lines[number]) - len(lines[number].lstrip()) > own):
                block.append(lines[number].strip())
                number += 1
            value = (" ".join(part for part in block if part) if raw.strip().startswith(">") else "\n".join(block).strip("\n"))
            (parent if indented and parent is not None else meta)[key] = value
            if not indented:
                parent = None
            continue
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


def step_name(text: str) -> str:
    """The bold name a step starts with, without its closing period; empty when the step has none."""

    match = STEP_NAME.match(text)
    return match.group(1).strip() if match else ""


def recorded_steps(body: str, where: str) -> int:
    """The number of steps a record covers: every step before the two closing steps."""

    names = [step_name(text) for _, text in procedure_steps(body)]
    if len(names) < len(CLOSING_STEPS) + 1 or tuple(names[-len(CLOSING_STEPS):]) != CLOSING_STEPS:
        raise SkillError(f"{where}: the Procedure must end with the steps {' and '.join(f'**{name}**' for name in CLOSING_STEPS)}, "
                         "in this order, after at least one step of its own work")
    return len(names) - len(CLOSING_STEPS)


def posix_dir(value: str) -> str:
    """A skills folder as the scripts name it: forward slashes, no leading `./` and no trailing slash."""

    text = value.replace("\\", "/").strip()
    while text.startswith("./"):
        text = text[2:]
    return text.rstrip("/")


def skills_dirs(root: Path, named: list[str] | None = None) -> list[str]:
    """The skills folders of the repository, relative to its root: the ones named, or every provider's in use.

    When the repository uses no provider, the result is the default folder, which may not exist yet.
    """

    if named:
        found = [posix_dir(name) for name in named]
    else:
        found = [provider["skills"] for provider in PROVIDERS
                 if any((root / path).exists() for path in (*provider["detect"], provider["skills"]))]
    unique = list(dict.fromkeys(found))
    return unique or [DEFAULT_SKILLS_DIR]


def skill_folders(skills_dir: Path) -> list[Path]:
    """Every folder of one skills folder that holds a SKILL.md, by name."""

    if not skills_dir.is_dir():
        return []
    return sorted(folder for folder in skills_dir.iterdir() if (folder / "SKILL.md").is_file())


def registration_block(root: Path, dirs: list[Path], skipped: list[str] | None = None) -> str:
    """The block an instruction file carries: one row per skill, linked to its copy in the first folder that holds it.

    A skill whose frontmatter cannot be read, or has no name or description, is left out and named in `skipped`, so
    one skill the user wrote in another form does not keep the others from being listed.
    """

    # A provider's skills folder that does not exist yet holds no skill to list and is not named.
    dirs = [skills_dir for skills_dir in dirs if skills_dir.is_dir()]
    rows: dict[str, str] = {}
    for skills_dir in dirs:
        for folder in skill_folders(skills_dir):
            try:
                meta, _ = read_skill(folder)
            except SkillError as exc:
                if skipped is not None:
                    skipped.append(f"{shown(folder, root)}: {exc}")
                continue
            name, description = meta.get("name"), meta.get("description")
            if not isinstance(name, str) or not isinstance(description, str) or not name or not description:
                if skipped is not None:
                    skipped.append(f"{shown(folder, root)}: SKILL.md has no name or no description")
                continue
            if name not in rows:
                cell = " ".join(description.split()).replace("|", "\\|")
                rows[name] = f"| [`{name}`]({shown(folder / 'SKILL.md', root)}) | {cell} |"
    names = ", ".join(f"`{shown(skills_dir, root)}/`" for skills_dir in dirs)
    if not rows:
        raise SkillError("the skills folders hold no skill to register")
    return "\n".join([
        BLOCK_START,
        "## Skills",
        "",
        f"This block is generated from the `SKILL.md` files in {names}: change those files, then register the skills again; do not edit it by hand.",
        "Every skills folder holds the same skills; each row links to one copy.",
        "",
        "When a request matches the description of a skill below, read that skill's `SKILL.md` in full and follow it; relative paths in that file resolve from its own folder.",
        "When no skill matches, work without one.",
        "",
        "| Skill | Description |",
        "| --- | --- |",
        *[rows[name] for name in sorted(rows)],
        BLOCK_END,
    ])


def registration_targets(root: Path, create: str | None = None) -> list[Path]:
    """The instruction files that carry the block, per the registration rule of the skill format.

    `create` names the file to create when the root has none of them; it changes nothing once one exists.
    Without it, a repository whose only provider is Claude Code gets CLAUDE.md, and any other gets AGENTS.md.
    """

    agents, claude = (root / name for name in INSTRUCTION_FILES)
    targets = [agents] if agents.is_file() else []
    if claude.is_file() and not (targets and loads_agents_md(claude, agents)):
        targets.append(claude)
    if targets:
        return targets
    if create is None:
        in_use = [provider["id"] for provider in PROVIDERS
                  if any((root / path).exists() for path in (*provider["detect"], provider["skills"]))]
        create = "CLAUDE.md" if in_use == ["claude"] else "AGENTS.md"
    return [root / create]


def loads_agents_md(claude: Path, agents: Path) -> bool:
    """True when CLAUDE.md brings AGENTS.md into the session itself: an `@AGENTS.md` import, or a link to that file.

    A sentence that only names AGENTS.md does not load it, so such a CLAUDE.md still needs the block of its own.
    """

    if claude.resolve() == agents.resolve():
        return True
    return re.search(r"(?m)(?:^|\s)@(?:\./)?AGENTS\.md(?:\s|$)", claude.read_text(encoding="utf-8")) is not None
