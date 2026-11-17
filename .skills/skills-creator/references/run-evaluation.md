# Run evaluation

The `skills-creator` skill owns how a run of a skill is recorded, how the record is evaluated and how the skill is improved from it.
Every skill of the [skill format](skill-format.md) applies this file through the first and the last steps of its procedure; the skill's own steps own the work in between.

The commands below name the `skills-creator` folder as `.skills/skills-creator`; a skill's own steps give the path that holds in its repository.

The purpose is one loop: a run records the decisions it made and how each step went, the evaluation looks for the decisions and steps that went wrong, and each wrong decision whose cause lies in a skill improves that skill, or the component that owns the cause, so the next run does not repeat it.

## When a run records

- Every run of a skill writes exactly one record, after its output is settled and before cleanup, whether the run completed, was blocked or failed.
- Asking the user for a decision or for content is not the end of a run: the run pauses, continues with the answers and records once.
- A request the skill did not take writes no record.
- A record is never edited: a record that proves wrong is corrected by a new record whose `supersedes` names it.

## Opening the run

The first step of a procedure runs `start` and keeps the returned `run_ref`: the name and the path of the skill, its `version`, a `digest` of its files, the number of steps of its procedure and the time the run started.
This is the version of the rules the run applies, and the record carries it unchanged, even when the run later improves the skill.

```powershell
python -B .skills/skills-creator/scripts/run_record.py start --skill <skill folder>
```

## Notes of the run

From the first step on, the run notes what the record needs, as it happens and not from memory at the end:

- **Steps.** For each step of the procedure: its status, as the [Record](#record) section lists them, and in one sentence what was done or why not.
- **Decisions.** Each choice that shaped the output, with the step that made it and its basis: a case chosen among the cases a step names, an assumption, a departure from a step, a question asked and the user's answer, a scope left out.
  The basis is what the decision rests on: a rule as `file#section`, a file or symbol that was read, a command and its result, or the user's words quoted.
  A decision without a basis is recorded as such; the evaluation treats it as a suspicion.

## Evaluating the run

- **Who.** A separate agent, when the host can create one, so that the run is not judged by the agent that made its decisions; the record states `mode: agent`.
  Its assignment lists exactly its inputs: the `run_ref`, the paths of the run's output, the notes of the run, the user's answers quoted and each command the procedure names with its result.
  When the host cannot create an agent, the agent that ran the skill evaluates after its output is settled, the record states `mode: self` and the `summary` says why.
- **Screening.** Every step and every decision is checked once against the skill as `run_ref` pins it.
  A step: it was carried out as the step says and in order; a skipped step names the condition of the skill that allows skipping it.
  A decision: its basis exists and says what the decision claims, the decision is one the step allows, and it agrees with the output and with the user's words.
  A point that fails a check is a suspicion; a point that passes is screened and is not opened again.
- **Settling a suspicion.** Read only what bears on it, then conclude it as a wrong decision or refute it.
  The evaluation does not redo the work of the run and does not produce its output again.
- **Defects in the output.** A wrong decision that left a defect in the output is returned to the agent that ran the skill, which fixes the output within the run, whatever the cause and whatever the [threshold](#improvement-threshold) says.

## Issues and causes

An issue is a wrong decision or a wrongly carried out step, with evidence, that meets the [improvement threshold](#improvement-threshold).
Each issue names its `subject` (the decision, or the step as `STEP-NN`), the `problem`, the `rule` it relates to as `file#section`, the `evidence` and an `issue_key`: a kebab-case key that describes the issue; an issue already present in an earlier record keeps its key.

Before classifying, look the earlier records up in one call, repeating the flags for every issue of the run:

```powershell
python -B .skills/skills-creator/scripts/run_record.py query --issue-key <key> --rule <file#section>
```

Classify by evidence, not by how often the issue repeated:

| Cause | When | Required improvement |
| --- | --- | --- |
| `instruction` | The rules, read as `run_ref` pins them, do not cover the case, lead to the wrong decision, conflict with each other or can be read two ways | Fix the rule in the file that owns it |
| `ineffective_fix` | An earlier record fixed an issue with the same key or the same rule, and the issue still happens | Find why that fix failed (wrong cause, does not cover this case, the step never reaches the rule), then replace or revert that fix itself, without stacking another; record `prior_fix` |
| `input` | The rule is right, but what the run was given is missing or wrong: the output of another skill, a template, a format reference, the repository's documentation | Fix where the input is produced |
| `execution` | The rule is clear, was read and leads to the right decision, but the run did not follow it | Make the point harder to miss: state it as a condition of when the step is done, or add it to the check of the verification step |

## Improvement threshold

A wrong decision is recorded as an issue, and improves a skill, only when all three hold:

1. Its cause lies in a skill or in a component a skill reads: the cause is `instruction`, `ineffective_fix` or `input`, or it is `execution` of a rule that an earlier record already holds under the same `issue_key` or the same rule.
2. It affects how the skill runs: when it opens, what a step reads, decides or produces, how the output is verified, recorded or handed off, what a run costs; not the content of one output.
3. It can recur in another run of the same kind.

A wrong decision that fails one of the three, such as a value that is wrong only in this run or the first slip against a clear rule, changes no file of a skill.
The record's `summary` states it in one sentence, with the reason it is below the threshold.

## Applying an improvement

Every issue that meets the threshold gets an improvement within the run, applied by the agent that evaluates:

1. Find the file that owns the cause and read the files that point to it: the skill's `SKILL.md`, its format reference, its template or its script, another skill whose output was the wrong input, or a file of `skills-creator` itself when the cause is the format, a template or a tool every skill shares.
2. Edit that one file per the [writing rules](writing-rules.md): replace the wrong passage in its general form, without piling a reminder on top of it, and do not copy the fix into files that only point to the owner.
3. Bump the `version` of each edited skill per [Frontmatter](skill-format.md#frontmatter).
4. Register the skills again when a `name` or a `description` changed, and run the validator on each edited skill ([Registration](skill-format.md#registration)).
5. Re-read the edited part against the [three scenarios](writing-rules.md#re-reading-against-three-scenarios), with the run that showed the issue as the first one.

Two kinds of improvement are not applied; the record holds them as `pending_user` and the final response asks the user:

- `safety`: the change would loosen, narrow, remove or work around a rule that limits deleting, overwriting, committing, pushing, deploying, sending or another action that is hard to undo or reaches outside the repository, a rule that protects secrets, or a rule that requires the user's decision.
- `repository`: the file that owns the cause lies outside the skills directory, such as the repository's instruction file outside its generated block or its documentation.

## Record

The agent that ran the skill writes the record, from its notes and from the issues and fixes the evaluation returned.
The record is one JSON object, written with `append`, which adds `schema`, `record_id` and `recorded_at`, rejects a record that departs from the table below and then checks every stored record as `check` does.
A run whose record is rejected is not complete.

```powershell
python -B .skills/skills-creator/scripts/run_record.py append --input <JSON file>
```

The input file is temporary: write it outside the skills directory, and remove it in the cleanup step.

Records are stored at `<skills directory>/.records/<skill>/<YYYY-MM-DD>.jsonl`, one record per line.
They describe the user's projects, so the tool creates `.records/.gitignore` with the single line `*` when that file does not exist: the records stay on the local machine until the user changes that file, which the tool never touches again.

| Field | Content |
| --- | --- |
| `run_ref` | The object `start` returned, copied as is |
| `request` | What the user asked, in short, in the user's words where possible |
| `outcome` | `status` (`completed`, `blocked` or `failed`) and `summary`: what the run produced, the wrong decisions below the threshold and, in `mode: self`, why no agent evaluated |
| `steps` | One entry per step of the procedure, in order: `step` (its number), `status` and `note`. The status is `done`, `skipped`, `blocked` or `failed`; `not_reached` for a step that a blocked or failed run never got to; `pending` for the steps that follow the writing of the record, such as the cleanup and the report |
| `decisions` | Each decision: `id` (`DEC-NN`), `step`, `decision` and `basis`; an empty array when the run decided nothing |
| `evaluation` | `mode` (`agent` or `self`) and `result` (`clean`, or `issues` when the record has issues) |
| `issues` | Each issue: `id` (`ISSUE-NN`), `issue_key`, `subject` (`DEC-NN` or `STEP-NN`), `cause`, `problem`, `rule`, `evidence`, and `prior_fix` (`<record_id>#FIX-NN`) only for `ineffective_fix` |
| `fixes` | Each improvement: `id` (`FIX-NN`), the `issues` it addresses, `status` (`applied` or `pending_user`), `reason` when pending (`safety` or `repository`), `files` (`path` and `section`), `summary`, and `checks`: the commands run after the fix, required when `applied` |
| `supersedes` | The `record_id` of the record this one corrects, or null |

Every issue belongs to at least one fix.
A complete record, as the input of `append`; values in `<...>` are placeholders:

```json
{
  "run_ref": {"skill": "<name>", "path": "<skill folder>", "version": "1.0.0", "digest": "<digest>", "steps": 3, "started_at": "<timestamp>"},
  "request": "<what the user asked>",
  "outcome": {"status": "completed", "summary": "<summary>"},
  "steps": [{"step": 1, "status": "done", "note": "<what was done>"},
            {"step": 2, "status": "skipped", "note": "<the condition of the skill that allowed skipping it>"},
            {"step": 3, "status": "pending", "note": "<what the step will do once the record is written>"}],
  "decisions": [{"id": "DEC-01", "step": 1, "decision": "<what was decided>", "basis": "<file#section, source read, command result or the user's words>"}],
  "evaluation": {"mode": "agent", "result": "issues"},
  "issues": [{"id": "ISSUE-01", "issue_key": "<kebab-case-key>", "subject": "DEC-01", "cause": "instruction",
              "problem": "<what is wrong>", "rule": "<file#section>", "evidence": "<evidence>"}],
  "fixes": [{"id": "FIX-01", "issues": ["ISSUE-01"], "status": "applied",
             "files": [{"path": "<file>", "section": "<section>"}], "summary": "<change>", "checks": ["<command>"]}],
  "supersedes": null
}
```

A run with no issue writes `issues: []`, `fixes: []` and `evaluation.result: "clean"`.

## Reporting

The final response of a run ends with its evaluation: the `record_id`, then for each applied improvement the issue, its cause, the file and section edited, the old and the new version and the change in one sentence; or the single sentence that no issue met the improvement threshold.
An improvement that is `pending_user` is described the same way, followed by the one decision the user is asked for.

## Reading earlier records

The records of a skill are read with `query --skill <name>`, the most recent ones with `--last <N>`.
A request to improve a skill from its records reads them first, groups the issues by `issue_key` and by `rule`, and treats each group as one cause to fix, per [Issues and causes](#issues-and-causes) and [Applying an improvement](#applying-an-improvement).
