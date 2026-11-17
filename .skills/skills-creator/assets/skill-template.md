---
name: {{name}}
description: "<What one run does and what it produces>. Use only when <the requests that open the skill>. Do not use <the nearby requests it must not take>."
metadata:
  id: {{id}}
  kind: skill
  version: 1.0.0
---

# <Name of the work>

Carries out one <unit of work>.
<If other documents own the decisions: each document or section and what it owns>.
This skill owns the order of the steps, the <artifact> format and the helper script.
<If a step names a section of another document: Where a step names a section, that section decides.>

## When to use

- <The requests that open the skill, by what the user's own words ask for>.
- Not for <each nearby request and where that work goes instead>.

## Resources

| Resource | Use |
| --- | --- |
| [`assets/{{artifact}}-template.md`](assets/{{artifact}}-template.md) | Template of one <artifact> |
| [`references/{{artifact}}-format.md`](references/{{artifact}}-format.md) | <Fields, sections, file naming and output location> |
| [`scripts/new_{{artifact_snake}}.py`](scripts/new_{{artifact_snake}}.py) | Creates the <artifact> file from the template, with <the computed values> filled in |
| [`run_record.py`]({{creator_rel}}/scripts/run_record.py) | Pins the skill version at the start of a run and writes the run's record |

## Procedure

Run the commands from the repository root.

1. **Open the run.** <What to read and apply before deciding anything>.
   Run the command below and keep the returned `run_ref` ([Opening the run]({{creator_rel}}/references/run-evaluation.md#opening-the-run)); from this step on, note each step and each decision with its basis ([Notes of the run]({{creator_rel}}/references/run-evaluation.md#notes-of-the-run)).

   ```powershell
   python -B {{creator_path}}/scripts/run_record.py start --skill {{skill_path}}
   ```

2. **<Step name>.** <What to do, when it is done, and the section that owns the rule the step applies>.
3. **Create the file** in the directory the user named, or by default in <the default directory> ([format](references/{{artifact}}-format.md#location-and-naming)):

   ```powershell
   python -B {{skill_path}}/scripts/new_{{artifact_snake}}.py --slug <slug> [--out-dir <dir>]
   ```

   Replace every `<...>` placeholder of the file per the [format](references/{{artifact}}-format.md#placeholders-in-the-template).
4. **Self-verify.** <The check of the file against the request and the format that the agent can perform; what is fixed before reporting>.
5. **Evaluate and record.** The run is evaluated, in a separate agent when the host can create one, and each issue that meets the threshold improves the skill within the run ([Evaluating the run]({{creator_rel}}/references/run-evaluation.md#evaluating-the-run), [Applying an improvement]({{creator_rel}}/references/run-evaluation.md#applying-an-improvement)); then exactly one record is written, which `append` also checks ([Record]({{creator_rel}}/references/run-evaluation.md#record)):

   ```powershell
   python -B {{creator_path}}/scripts/run_record.py append --input <JSON file>
   ```

6. **Clean up.** <What the run created temporarily and removes>.
7. **Report.** <The file written, how it was verified and what remains open>, then the evaluation of the run ([Reporting]({{creator_rel}}/references/run-evaluation.md#reporting)).
