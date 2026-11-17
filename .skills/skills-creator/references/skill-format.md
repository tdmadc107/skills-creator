# Skill format

The `skills-creator` skill owns how a skill is laid out, named, stored and registered.
How the content of a skill is worded belongs to the [writing rules](writing-rules.md); how a run of a skill is recorded, evaluated and turned into improvements belongs to [Run evaluation](run-evaluation.md).

## Location and naming

- Skills directory: the directory the user names; when the user names none, the directory where the repository already keeps skills of this format; when there is none, `.skills/` at the repository root.
- Skill folder: `<skills directory>/<name>/`.
  The `name` is ASCII kebab-case (lowercase letters, digits and single hyphens), at most 64 characters, and unique in the skills directory.
  It names the work the skill carries out; skills that belong to one family share a prefix.
- Entry point: `SKILL.md` in the skill folder.
  An agent reads it first and reads every other file of the skill only when a step needs it.
- Creating a skill never overwrites an existing one (the helper script refuses); an existing skill is adjusted by editing its files.
- Every skill depends on the `skills-creator` folder of the same repository: its steps run the record tool there and link to its run evaluation.
  A skill is therefore created by the copy of `skills-creator` that lives in the repository, and is moved to another repository together with it.
- The records of the runs live outside the skill folders, in `<skills directory>/.records/` ([Record](run-evaluation.md#record)).

## The two sizes

| Size | Files | Choose when |
| --- | --- | --- |
| Thin | `SKILL.md` only | The skill only orders the steps of a kind of work: a run produces no file of a fixed form, or another document owns that form |
| Full | `SKILL.md`, `assets/`, `references/` and, when a tool has something to compute or check, `scripts/` | Each run produces a file of a fixed form, the artifact, that later work reads |

A full skill names its resources after the artifact, in kebab-case for Markdown files and with underscores for scripts:

```text
<name>/
  SKILL.md
  assets/<artifact>-template.md        template of one artifact
  references/<artifact>-format.md      how the artifact is laid out, named and stored
  scripts/new_<artifact>.py            creates the artifact from the template
```

- The template and its format reference always come together.
- A script exists only for what a tool can compute or check.
  When a skill has nothing of that kind, remove the script, its folder and its row in the Resources table.
- A resource folder that exists holds at least one file, and the skill folder holds no other folder.
- Knowledge that belongs to one repository lives in that repository's own documentation, not in a skill.

## Frontmatter

| Field | Value |
| --- | --- |
| `name` | The folder name |
| `description` | One line of at most 1024 characters, in double quotes, in the three parts of the [writing rules](writing-rules.md#description) |
| `metadata.id` | Path of the skill folder from the repository root, for example `.skills/<name>` |
| `metadata.kind` | `skill` |
| `metadata.version` | `<major>.<minor>.<patch>`, starting at `1.0.0` |

Write the frontmatter in the YAML subset the validator reads: one `key: value` per line, the `metadata` keys indented by two spaces, a value in quotes when it contains `:` or `#`.
A family of skills may add its own keys under `metadata`; the validator ignores them.

Every edit of a skill bumps its `version`: the patch number for wording that changes no behavior, the minor number for a step, a case or a resource added, the major number when the requests the skill takes or the form of its output change.

## Body

The body has these five parts, in this order, and no level-two section other than the three named below.

1. **Title.** The name of the work, not the skill ID.
2. **Opening paragraph.** One sentence that says what one run carries out, then who owns what: the documents that own the decisions, and what the skill itself owns (the order of the steps; for a full skill also the artifact format and the helper script).
   When the steps point to sections of other documents, the paragraph ends with the sentence that those sections decide.
3. **`## When to use`.** One list item for the requests that open the skill, and one for the nearby requests it must not take, each with where that work goes instead.
4. **`## Resources`.** A table with the columns `Resource` and `Use`: one row per file of `assets/`, `references/` and `scripts/`, each linked, and one row per tool outside the skill that a step runs.
   Every skill has the row of the record tool, `scripts/run_record.py` of `skills-creator`, linked by its relative path.
   A file whose name starts with an underscore is shared code of the scripts and gets no row.
5. **`## Procedure`.** The steps of one run, numbered from 1.
   Each step starts with its name in bold, then says what to do and links to the section that owns the rule it applies.
   A command sits in a fenced code block under its step, with `<...>` for the values the agent supplies; when the procedure has commands, a line above the list says where they run from.
   The first step opens the run: it reads what the run needs and runs `start` of the record tool ([Opening the run](run-evaluation.md#opening-the-run)).
   The last steps verify the output, evaluate the run and write its record ([Run evaluation](run-evaluation.md)), clean up what the run created temporarily and report.
   When the skill must not start a following kind of work on its own, the last step says so.

## Format reference

`references/<artifact>-format.md` of a full skill opens with what the skill owns and has these sections:

- **Location and naming**: the output directory and its default, the file name pattern, the form of slugs and timestamps, and that creating never overwrites.
- **Frontmatter**: a table of every field with its value or its allowed values, when the artifact has frontmatter.
- **Body**: the sections in their order, and the form of the lines that later work reads one by one.
- **Placeholders in the template**: the two kinds below.

## Output template

`assets/<artifact>-template.md` of a full skill is the artifact with its variable parts as placeholders:

- `{{name}}`: a value the helper script computes and fills in, such as a name, an ID or a timestamp.
- `<...>`: content the agent writes from the decisions of the run.
  A line of the form `<If ...: ...>` stays only when its condition holds.

A line of the template is one unit that is read on its own, such as a `Label: value` line; it is not split further.

## Helper script

A script in `scripts/` follows these conventions:

- Python 3.9 or later, standard library only, run as `python -B <path>` from the repository root.
- A module docstring that says what the script does and names the reference that owns its rules; the script fills only what a tool can compute and leaves every `<...>` placeholder to the agent.
- Arguments through `argparse`, with `--root` for the repository root, so that a test can run it against a temporary directory.
- Inputs are checked before anything is written, and one bad input writes nothing.
- A script that creates a file refuses when that file exists.
- It prints one JSON object with `passed`, the paths it wrote relative to the root, or `errors`, and exits with 0 when `passed` is true and 1 otherwise.

## Registration

Every skill is registered in the repository's instruction file, the file the host loads in every session, so that an agent finds the skill whatever directory the host looks for skills in.

- **Which file.** `AGENTS.md` when the repository root has it.
  `CLAUDE.md` when the root has it, unless `AGENTS.md` exists and `CLAUDE.md` names it: such a `CLAUDE.md` already loads the block from `AGENTS.md`.
  So both files carry the block when both exist and `CLAUDE.md` does not name `AGENTS.md`.
  When the root has neither, create `AGENTS.md`, or `CLAUDE.md` when the user asks for that file.
- **What.** One block between the markers `<!-- skills:start -->` and `<!-- skills:end -->`: a `Skills` heading, the instruction to read and follow the `SKILL.md` of the skill whose description matches the request, and a table with one row per skill of the skills directory, its link and its description.
- **When.** After a skill is created, after its `name` or `description` changes, and after a skill is removed.
- **How.** The block is generated from the `SKILL.md` files by `scripts/register_skills.py` and is never edited by hand.
  The script replaces the block when the file has one, appends it otherwise, and leaves the rest of the file as it is.
