# Changelog

Every notable change to skills-generator is recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

To be released as 2.0.0: the skill moves from `.skills/` to the skills folders of the agent providers, so the installer and the scripts work differently.

### Changed

- The skill and every skill it creates live in the skills folder of each agent provider the project uses, named `skills`, instead of `.skills/`:
  - `.agents/skills/` for Codex CLI, Antigravity and other agents that read `.agents/` (found by `.agents/`, `.codex/` or `.agent/`);
  - `.claude/skills/` for Claude Code (`.claude/` or `CLAUDE.md`);
  - `.cursor/skills/` for Cursor (`.cursor/`);
  - `.gemini/skills/` for Gemini CLI (`.gemini/` or `GEMINI.md`);
  - `.github/skills/` for GitHub Copilot (`.github/skills/`, `.github/copilot-instructions.md` or `.github/instructions/`, but not `.github/` alone).

  An existing skills folder is used as it is, a missing one is created, and a project that uses no provider gets `.agents/skills/`.
- With several providers, every skills folder holds a full copy of every skill, identical but for the paths of its own folder.
  `new_skill.py` creates a skill in every skills folder at once, the procedure and the run evaluation make every change in every copy, and `validate_skill.py` reports a copy that is missing or differs.
- `npx skills-generator` installs or updates the copy of every provider in use; an update that meets a file changed in any copy changes nothing anywhere unless `--force` is given.
- When the project has neither `AGENTS.md` nor `CLAUDE.md`, `CLAUDE.md` is created if Claude Code is the only provider in use, otherwise `AGENTS.md`; creating `CLAUDE.md` puts Claude Code in use, so its skills folder gets the skill too.
- The registration block lists each skill once, linked to its copy in the first skills folder, and names only the skills folders that exist.
- The installer copies every skill of the skill format into a skills folder that lacks it, such as the folder of a provider added after skills were created, with the paths of that folder; it never overwrites a folder and leaves skills of another form where they are.
- Records are written next to the copy of the skill that ran, `<skills folder>/.records/`, and `run_record.py check` and `query` read the records of every skills folder together.
- The scripts find the skills folders themselves; `--skills-dir` of `new_skill.py`, `register_skills.py` and `run_record.py` is repeatable and names other folders instead.
- The README says to run the installer at the root folder of the project.

### Fixed

- The frontmatter reader takes `>` and `|` block values, as in a skill whose description spans several lines, and the registration leaves out, and names, a skill it cannot read instead of failing for every skill.

### Deprecated

- A copy that version 1.0.0 installed in `.skills/skills-generator/` is reported by the installer and left as it is; agents do not read `.skills/`, so move the skills created there into the skills folders, then delete `.skills/`.

### Removed

- The installer's `--skills-dir` option: the skills folders follow the providers the project uses.

## [1.0.0] - 2026-11-17

The first release.

### Added

- The `skills-generator` skill (`.skills/skills-generator/SKILL.md`): it creates a skill from a request in plain words, adjusts an existing one, or improves one from its run records, in eleven steps from opening the run to the report.
  It asks only about the decisions that change the skill and that the repository does not answer, and a new skill runs only when the user asks for the work it carries out.
- The skill format (`references/skill-format.md`): a skill is a folder whose `SKILL.md` holds the frontmatter (`name`, `description`, `metadata.id`, `metadata.kind`, `metadata.version`), `When to use`, `Resources` and a numbered `Procedure`.
  A thin skill has `SKILL.md` only; a full skill, whose runs produce a file of a fixed form, adds an output template, its format reference and, when a tool has something to compute, a helper script.
  Every procedure opens the run with the record tool and ends with **Clean up**, **Evaluate and record** and **Report**.
- The writing rules (`references/writing-rules.md`): a description in three parts (what a run does, `Use only when`, `Do not use`), one owner per rule, rules in their general form, steps that say what to do and when they are done, one sentence per line, and a re-read of each finished skill against three scenarios.
- Registration: every skill is listed in one generated block of the repository's `AGENTS.md` or `CLAUDE.md`, whichever it has; when it has neither, `AGENTS.md` is created, or `CLAUDE.md` on request.
  The block is replaced in place and the rest of the file is left as it is, line endings included.
- Run records and evaluation (`references/run-evaluation.md`): each run of a skill notes its steps and its decisions with their basis, is evaluated, by a separate agent when the host can create one, and writes one record to `.skills/.records/<skill>/<YYYY-MM-DD>.jsonl`, which Git ignores by default.
  Each issue is classified as `instruction`, `ineffective_fix`, `input` or `execution`, and one that can recur and affects how the skill runs is fixed within the run in the file that owns its cause; a change that would loosen a safety rule, or that lies outside the skills directory, waits for the user.
- Templates (`assets/`) for the `SKILL.md` of a thin and of a full skill, a format reference, an output template and a helper script.
- Scripts (`scripts/`, Python 3.9 or later, standard library only), each printing one JSON object with `passed`:
  - `new_skill.py` creates a skill folder from the templates and never overwrites one.
  - `register_skills.py` writes or checks the registration block.
  - `validate_skill.py` checks the frontmatter, the sections, the steps, the resources, the links, the record tool and the registration of a skill.
  - `run_record.py` opens a run, writes and checks records, and looks earlier records up by skill, issue key or rule.
- The npm installer (`npx skills-generator`): the first run copies the skill into `.skills/skills-generator/` and registers it; a later run updates it, and keeps every file the runs changed in the repository unless `--force` is given.
  It writes `.skills/skills-generator/.install.json` with the hash of each installed file, and takes `--skills-dir`, `--create`, `--force`, `--root`, `--version` and `--help`.
- Continuous integration (`.github/workflows/ci.yml`) on Python 3.9 and 3.13 and on Node 18, 22 and 24, and a publish workflow (`.github/workflows/publish.yml`) that releases to npm on a `v<version>` tag of `main`, once the tests pass and the tag, `package.json`, `SKILL.md` and this changelog agree on the version.
- Rulesets to import into GitHub (`.github/rulesets/`) that protect `main`, keep the release tags and the creation of branches to the owner, and require every CI job, with a `CODEOWNERS` file.

[1.0.0]: https://github.com/tdmadc107/skills-creator/releases/tag/v1.0.0
