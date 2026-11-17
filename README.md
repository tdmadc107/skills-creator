# skills-creator

A skill that creates other skills, in one standard format: a folder whose `SKILL.md` says when the skill applies and gives a numbered procedure, with a template, a format reference and a helper script when each run of the skill produces a file of a fixed form.
The format is the one the skills of the PIRL framework follow, taken on its own: `skills-creator` depends on no framework, and the skills it creates carry their own rules.

Every skill it creates is registered in the repository's `AGENTS.md` or `CLAUDE.md`, whichever the repository has; when it has neither, `AGENTS.md` is created.

Every skill it creates also improves from its own runs: each run records the decisions it made and how each step went as one JSON line, the record is evaluated for wrong decisions and wrongly carried out steps, and each issue whose cause lies in a skill is fixed in the file that owns the cause.

## What the repository holds

```text
.skills/skills-creator/
  SKILL.md                       when the skill applies and the procedure of one skill creation task
  references/skill-format.md     location and naming, the two sizes, frontmatter, body, resources, registration
  references/writing-rules.md    how a description, a rule and a step are worded; the three scenarios of the re-read
  references/run-evaluation.md   when a run records, how it is evaluated, the causes, the threshold, the improvements, the record fields
  assets/                        templates of SKILL.md (thin and full), of a format reference, an output template and a helper script
  scripts/new_skill.py           creates a skill folder from the templates
  scripts/register_skills.py     writes the block that lists every skill into AGENTS.md or CLAUDE.md
  scripts/validate_skill.py      checks the structure of a skill, its links and its registration
  scripts/run_record.py          opens a run, writes its record, checks the stored records and looks earlier ones up
AGENTS.md                        instruction file of this repository; it registers the skill
tests/                           tests of the scripts and of the skill itself
```

## Using it in a repository

1. Copy the folder `.skills/skills-creator/` into the `.skills/` folder of the repository.
2. Register it, from the root of that repository:

   ```powershell
   python -B .skills/skills-creator/scripts/register_skills.py
   ```

3. Ask the agent for a skill in your own words, for example "create a skill that writes release notes".
   The agent finds `skills-creator` through the instruction file and follows its [`SKILL.md`](.skills/skills-creator/SKILL.md).

The scripts need Python 3.9 or later and nothing outside the standard library.

The skills it creates run the record tool of this folder and link to its run evaluation, so they stay in the same skills directory as `skills-creator`.
Records are written to `.skills/.records/<skill>/<YYYY-MM-DD>.jsonl` and are ignored by Git through `.skills/.records/.gitignore`, which the tool creates once and never changes afterwards: edit that file to share the records with a team.

## The scripts on their own

```powershell
python -B .skills/skills-creator/scripts/new_skill.py --name <name> --size <thin|full> [--artifact <artifact>] [--skills-dir <dir>]
python -B .skills/skills-creator/scripts/register_skills.py [--skills-dir <dir>] [--file <AGENTS.md|CLAUDE.md>] [--check]
python -B .skills/skills-creator/scripts/validate_skill.py --path <skill folder or skills directory> [--skip-registration]
python -B .skills/skills-creator/scripts/run_record.py start --skill <skill folder>
python -B .skills/skills-creator/scripts/run_record.py append --input <JSON file>
python -B .skills/skills-creator/scripts/run_record.py check [--skills-dir <dir>]
python -B .skills/skills-creator/scripts/run_record.py query [--skill <name>] [--issue-key <key>] [--rule <file#section>] [--last <N>] [--all]
```

Each script prints one JSON object with `passed`, and exits with 0 when it is true.
The validator checks structure only; the wording of a skill is re-read against the three scenarios of the [writing rules](.skills/skills-creator/references/writing-rules.md#re-reading-against-three-scenarios).

## Working on this repository

Start from [`AGENTS.md`](AGENTS.md) and run the tests from the repository root:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
```
