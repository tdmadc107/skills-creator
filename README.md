<div align="center">

# 🧩 skills-generator

**Turn any way of working into an agent skill: one standard format, registered where agents look, and better after every run.**

[![npm version](https://img.shields.io/npm/v/skills-generator?color=2f6fe4&label=npm)](https://www.npmjs.com/package/skills-generator)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![node](https://img.shields.io/badge/node-%E2%89%A518-339933?logo=node.js&logoColor=white)](https://nodejs.org)
[![python](https://img.shields.io/badge/python-%E2%89%A53.9-3776AB?logo=python&logoColor=white)](https://www.python.org)

[⚡ Quick Start](#-quick-start) · [🧩 Skill Format](#-what-a-generated-skill-looks-like) · [🔁 Self-improvement](#-how-skills-improve-themselves) · [🔧 Options](#-installer-options) · [📖 Docs](#-documentation)

</div>

---

## 🤔 Why skills-generator?

`skills-generator` is itself an agent skill: you describe the work in plain words, and your coding agent writes a skill for it.

- 📐 **One format for every skill.** Each skill is a folder whose `SKILL.md` says when it applies and gives a numbered procedure, with a template, a format reference and a helper script when each run produces a file of a fixed form.
- 📌 **Found by every agent.** Each skill is copied into the skills folder of every agent provider your project uses (`.claude/skills/`, `.agents/skills/`, `.cursor/skills/`…) and listed in `AGENTS.md` or `CLAUDE.md`.
- 🔁 **Self-improving.** Each run of a generated skill records its steps and decisions, an evaluation looks for what went wrong, and the skill is fixed at the root cause.
- ✅ **Checked, not guessed.** A validator checks the structure of every skill, and each new skill is re-read against three scenarios before it is handed over.
- 🔒 **Safe updates.** Updating the package never overwrites the improvements your runs made, unless you ask for it.

The format is drawn from the skills of the [PIRL framework](https://www.npmjs.com/package/pirl-framework) and stands on its own: no framework to install, and a generated skill carries the rules of its own work.
It calls no model and needs no API key: your agent runs it with the model you already chose.

---

## ⚡ Quick Start

> **Run it at the root folder of your project**, the folder that holds `.git`, `.claude/`, `.agents/` or your `AGENTS.md` / `CLAUDE.md`.

```powershell
cd path/to/your-project
npx skills-generator
```

The installer looks for the agent providers your project uses and copies the skill into the skills folder of each one:

| Your project has | The skill goes to |
| --- | --- |
| `.agents/`, `.codex/` or `.agent/` (Codex CLI, Antigravity…) | `.agents/skills/skills-generator/` |
| `.claude/` or `CLAUDE.md` (Claude Code) | `.claude/skills/skills-generator/` |
| `.cursor/` (Cursor) | `.cursor/skills/skills-generator/` |
| `.gemini/` or `GEMINI.md` (Gemini CLI) | `.gemini/skills/skills-generator/` |
| `.github/skills/`, `.github/copilot-instructions.md` or `.github/instructions/` (GitHub Copilot) | `.github/skills/skills-generator/` |
| None of them | `.agents/skills/skills-generator/`, created |

- 📁 An existing skills folder counts as its provider being in use and is used as it is; a missing one is created, named `skills`.
- 🐙 A `.github/` folder that holds only workflows does not count as GitHub Copilot.
- 🧩 With several providers, each one gets a full copy, and every skill you create or improve later is kept identical in every copy.
- ➕ Add a provider later and run the installer again: the new provider gets `skills-generator` and a copy of every skill you created.
- 🤝 Skills you wrote yourself for one provider stay where they are, and are listed in the instruction file too.
- 📝 The skills are also listed in `AGENTS.md` or `CLAUDE.md`, whichever the project has; with neither, `CLAUDE.md` is created when Claude Code is your only provider, `AGENTS.md` otherwise.

Commit the skills folders and the instruction file so the whole team shares the same skills; the run records stay out of Git through the `.records/.gitignore` of each skills folder.
Then ask your agent in plain words:

| You want to | Example request |
| --- | --- |
| Create a skill | "Create a skill that writes release notes from the merged pull requests" |
| Turn a habit into a skill | "Turn the way we review database migrations into a skill" |
| Adjust a skill | "Make the release-notes skill also list breaking changes" |
| Improve a skill from its runs | "Improve the release-notes skill from its run records" |

The agent asks only about the decisions it cannot settle from your repository, writes the skill, registers it and validates it.
A new skill runs only when you ask for the work it carries out.

---

## 🧩 What a generated skill looks like

| Size | Files | Chosen when |
| --- | --- | --- |
| 📄 Thin | `SKILL.md` | The skill orders the steps of a kind of work, and no run produces a file of a fixed form |
| 📦 Full | `SKILL.md`, `assets/`, `references/` and, when a tool has something to compute, `scripts/` | Each run produces a file of a fixed form that later work reads |

```text
.claude/skills/                         one skills folder per provider, each with the same skills
  release-notes/
    SKILL.md                            frontmatter, When to use, Resources, Procedure
    assets/release-note-template.md     template of one release note
    references/release-note-format.md   how a release note is laid out, named and stored
    scripts/new_release_note.py         creates a release note from the template
  skills-generator/                     this skill, which every generated skill relies on
  .records/                             the records of the runs made from this folder, kept out of Git
.agents/skills/                         the same skills, for the providers that read .agents/
```

Every procedure opens the run with the record tool and ends with the same three steps: **Clean up → Evaluate and record → Report**.

---

## 🔁 How skills improve themselves

```text
Open the run ──▶ the skill's own steps ──▶ Clean up ──▶ Evaluate and record ──▶ Report
   │                    │                                     │
   │ pins the version   │ notes each step and each            │ screens every step and decision,
   │ of the skill       │ decision with its basis             │ fixes the cause, writes one record
```

- 🕵️ **Evaluated by another agent.** When the host can create one, a separate agent screens the run instead of the agent that made its decisions.
- 🧭 **Fixed at the cause.** Each issue is classified as `instruction`, `ineffective_fix`, `input` or `execution`, and the file that owns the cause is fixed: the skill, its template, another skill, or `skills-generator` itself.
- 🎯 **Only what recurs.** A wrong decision changes a skill only when it affects how the skill runs and can happen again; a mistake specific to one run is fixed in the output and noted.
- 🛑 **Asks before it loosens.** A change that would weaken a safety rule, or that lies outside the skills folders, waits for your decision.
- 🗂️ **Searchable history.** Records are JSON lines in `<skills folder>/.records/<skill>/<date>.jsonl`, read together across the skills folders, and earlier fixes are looked up before a new one is made.

The whole contract lives in [`run-evaluation.md`](.agents/skills/skills-generator/references/run-evaluation.md).

---

## 🔧 Installer options

| Command | What it does |
| --- | --- |
| `npx skills-generator` | Installs the skill for every provider of the project; once installed, updates every copy and keeps the files your runs changed |
| `npx skills-generator@latest` | The same with the newest version, so that `npx` does not reuse the one it cached |

Options: `--create <AGENTS.md|CLAUDE.md>` (the file to create when the project has neither), `--force` (also replace the files changed in the project), `--root <dir>` (the root folder of the project, when you run it from elsewhere), `--version`, `--help`.

When an update meets a file your runs improved, in any copy, it lists the file and changes nothing: merge it by hand in every copy, or run again with `--force` after committing to keep a copy.
Each copy holds an `.install.json`, the hashes that updates compare with; commit it with the skill.
A provider you add later gets its copy on the next run.

The installer needs Node 18 or later; the skill's scripts need Python 3.9 or later and nothing outside the standard library.
Without Node, copy `.agents/skills/skills-generator/` from the package into the skills folder of each provider, replace `.agents/skills/skills-generator` with the path of that copy in every file of the copy, then run `python -B <skills folder>/skills-generator/scripts/register_skills.py` at the root folder of the project.

---

## 🛠️ Scripts

The agent runs them for you; each prints one JSON object with `passed` and exits with 0 when it is true.

| Script | What it does |
| --- | --- |
| `new_skill.py --name <name> --size <thin\|full> [--artifact <name>]` | Creates the skill from the templates in every skills folder |
| `register_skills.py [--create <AGENTS.md\|CLAUDE.md>] [--check]` | Lists every skill in the instruction file, or checks that the list is current |
| `validate_skill.py --path <skill or skills folder>` | Checks the structure, the links, the copies and the registration of a skill |
| `run_record.py <start\|append\|check\|query>` | Opens a run, writes its record, checks the stored records, looks earlier ones up |

They live in `scripts/` of each copy of `skills-generator`, find the skills folders of the project themselves, and take `--root <dir>`; `--skills-dir <dir>` names other folders instead.

---

## 📖 Documentation

| To learn about | Read |
| --- | --- |
| The procedure of one skill creation task | [`SKILL.md`](.agents/skills/skills-generator/SKILL.md) |
| Layout, naming, frontmatter, body, registration | [Skill format](.agents/skills/skills-generator/references/skill-format.md) |
| How descriptions, rules and steps are worded | [Writing rules](.agents/skills/skills-generator/references/writing-rules.md) |
| Records, evaluation and improvements | [Run evaluation](.agents/skills/skills-generator/references/run-evaluation.md) |
| What changed in each version | [`CHANGELOG.md`](CHANGELOG.md) |
| Tests, releases and repository protection | [`MAINTAINING.md`](MAINTAINING.md) |

---

## 📄 License

[MIT](LICENSE) © tdmadc107
