---
name: skills-generator
description: "Creates or adjusts an agent skill in the standard skill format. Turns a request for a skill into a skill folder, copied into the skills folder of every agent provider the repository uses, whose SKILL.md holds the frontmatter, when the skill applies and a numbered procedure, with a template, a format reference and a helper script when each run of the skill produces a file of a fixed form, then registers every skill in the repository's AGENTS.md or CLAUDE.md, creating that file when the repository has neither, and validates the structure. Every skill it creates records the decisions and the steps of each run, has the record evaluated and is improved from the issues found. Use only when the user's own words ask to create, scaffold, restructure or adjust a skill, or to improve a skill from its run records. Do not use to run an existing skill, to answer a question about skills that only needs an explanation, or to write agent instructions that are not a skill."
metadata:
  id: .agents/skills/skills-generator
  kind: skill
  version: 2.0.1
---

# Skill creation

Carries out one skill creation task: a new skill, or an adjustment of an existing one.
The [skill format](references/skill-format.md) owns how a skill is laid out, named, stored and registered; the [writing rules](references/writing-rules.md) own how its content is worded; [Run evaluation](references/run-evaluation.md) owns how a run of a skill is recorded, evaluated and turned into improvements.
This skill owns the order of the steps, the templates and the helper scripts.
Where a step names a section, that section decides.
The skill depends on no other framework.
A skill it creates carries the rules of its own work, links to a document of the repository only where that document already owns a rule, and takes the recording and the evaluation of its runs from this skill.

## When to use

- The user's own words ask to create a skill, to turn a way of working into a skill, to restructure or adjust an existing skill, or to improve a skill from its run records.
- Not for running a skill that exists, which follows that skill's own `SKILL.md`; not for a question about skills that only needs an explanation, which is answered directly; not for agent instructions that are not a skill, such as the rules of an instruction file, which are edited in that file; not for the improvements the evaluation of a run applies, which follow [Applying an improvement](references/run-evaluation.md#applying-an-improvement) inside that run.

## Resources

| Resource | Use |
| --- | --- |
| [`references/skill-format.md`](references/skill-format.md) | Location and naming, the two sizes, frontmatter, body, the resources of a full skill and registration |
| [`references/writing-rules.md`](references/writing-rules.md) | How the description, the rules and the steps are worded, and the three scenarios the finished skill is re-read against |
| [`references/run-evaluation.md`](references/run-evaluation.md) | When a run records, how it is evaluated, the causes of an issue, the improvement threshold, how an improvement is applied and the record fields |
| [`assets/skill-thin-template.md`](assets/skill-thin-template.md) | Template of the `SKILL.md` of a thin skill |
| [`assets/skill-template.md`](assets/skill-template.md) | Template of the `SKILL.md` of a full skill |
| [`assets/output-template.md`](assets/output-template.md) | Template of the output template a full skill keeps in `assets/` |
| [`assets/format-template.md`](assets/format-template.md) | Template of the format reference a full skill keeps in `references/` |
| [`assets/script-template.py`](assets/script-template.py) | Template of the helper script a full skill keeps in `scripts/` |
| [`scripts/new_skill.py`](scripts/new_skill.py) | Creates the skill folder from the templates, with the name, the id, the resource file names and the skill path filled in |
| [`scripts/register_skills.py`](scripts/register_skills.py) | Writes the block that lists every skill into the repository's instruction file, or checks it with `--check` |
| [`scripts/validate_skill.py`](scripts/validate_skill.py) | Checks the structure of a skill, its links and its registration |
| [`scripts/run_record.py`](scripts/run_record.py) | Pins the skill version at the start of a run, writes the run's record, checks the stored records and looks earlier ones up |

## Procedure

Run the commands from the root of the repository that receives the skill; use `python3` where `python` is not on the PATH.
The commands name this skill's folder as `.agents/skills/skills-generator`; in a copy in another skills folder, they name that copy.
The scripts find the skills folders of the repository themselves ([Location and naming](references/skill-format.md#location-and-naming)).

1. **Open the run.** Read the [skill format](references/skill-format.md) and the [writing rules](references/writing-rules.md) in full.
   Read the repository's instruction file, when it has one, and the `SKILL.md` of every skill already in one of the skills folders ([Location and naming](references/skill-format.md#location-and-naming)), together in one step.
   Run the command below and keep the returned `run_ref` ([Opening the run](references/run-evaluation.md#opening-the-run)); from this step on, note each step and each decision with its basis ([Notes of the run](references/run-evaluation.md#notes-of-the-run)).

   ```powershell
   python -B .agents/skills/skills-generator/scripts/run_record.py start --skill .agents/skills/skills-generator
   ```

2. **Analyze the request.** Settle what one run of the skill carries out, the requests that open it and the nearby requests it must not take, what a run produces, which document owns each decision of the work ([One owner per rule](references/writing-rules.md#one-owner-per-rule)), and the steps of a run.
   Investigate what the repository and the conversation already answer.
   Ask only about the missing decisions that change the skill, all of them in one message, and wait for the answers; a request that overlaps an existing skill is one of them ([Description](references/writing-rules.md#description)).
   When the user asks to improve a skill from its run records, read them first and group their issues per [Reading earlier records](references/run-evaluation.md#reading-earlier-records).
3. **Choose the size and the name** ([The two sizes](references/skill-format.md#the-two-sizes), [Location and naming](references/skill-format.md#location-and-naming)); for a full skill, also the name of the artifact.
4. **Scaffold the skill.**
   The script creates the skill in every skills folder at once.
   When the user asks to adjust or improve an existing skill, skip this step: steps 5 to 8 apply to the files that change, in every copy.

   ```powershell
   python -B .agents/skills/skills-generator/scripts/new_skill.py --name <name> --size <thin|full> [--artifact <artifact>]
   ```

5. **Write the content.** Replace every `<...>` placeholder of `SKILL.md` per the [Body](references/skill-format.md#body) and [Frontmatter](references/skill-format.md#frontmatter) sections and the [writing rules](references/writing-rules.md); a line of the form `<If ...: ...>` stays only when its condition holds.
   Keep the steps that open the run and that evaluate and record it as the template gives them, and renumber them when steps are added between them.
   For a full skill, write the [format reference](references/skill-format.md#format-reference) first, then the [output template](references/skill-format.md#output-template), then adapt the [helper script](references/skill-format.md#helper-script) to what a tool can compute, or remove it when there is nothing to compute.
   Run each script once against a temporary directory and read its output.
   Write the content in one copy, then give every other copy the same content with the paths of its own skills folder ([Location and naming](references/skill-format.md#location-and-naming)).
   An adjusted skill gets its `version` bumped per [Frontmatter](references/skill-format.md#frontmatter), in every copy.
6. **Register the skills** in the instruction file that [Registration](references/skill-format.md#registration) picks; pass `--create <file>` only when the repository has neither file and the user names the one to create:

   ```powershell
   python -B .agents/skills/skills-generator/scripts/register_skills.py [--create <AGENTS.md|CLAUDE.md>]
   ```

7. **Validate**, then fix and rerun until the validator passes:

   ```powershell
   python -B .agents/skills/skills-generator/scripts/validate_skill.py --path <skill folder>
   ```

8. **Re-read against the three scenarios** of the [writing rules](references/writing-rules.md#re-reading-against-three-scenarios).
   A scenario that fails goes back to step 5; after a change of the `name` or the `description`, steps 6 and 7 run again.
9. **Clean up** the temporary directories and files the run created; the notes of the run stay for the next step.
10. **Evaluate and record.** Have the run evaluated ([Evaluating the run](references/run-evaluation.md#evaluating-the-run)) and its issues improved ([Applying an improvement](references/run-evaluation.md#applying-an-improvement)), then write exactly one record ([Record](references/run-evaluation.md#record)):

    ```powershell
    python -B .agents/skills/skills-generator/scripts/run_record.py append --input <JSON file>
    ```

11. **Report** the skill folder and each file written, the instruction file that registers the skill, the result of the validator, the three scenarios read and what remains open, then the evaluation of the run ([Reporting](references/run-evaluation.md#reporting)).
    Stop there: the new skill runs only when the user asks for the work it carries out.
