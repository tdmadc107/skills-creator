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
<If other documents own the decisions: each document or section and what it owns; this skill owns only the order of the steps>.
<If no other document owns them: this skill owns the rules of the work, stated in its steps, and the order of the steps>.
<If a step names a section of another document: Where a step names a section, that section decides.>

## When to use

- <The requests that open the skill, by what the user's own words ask for>.
- Not for <each nearby request and where that work goes instead>.

## Resources

| Resource | Use |
| --- | --- |
| [`run_record.py`]({{creator_rel}}/scripts/run_record.py) | Pins the skill version at the start of a run and writes the run's record |

## Procedure

Run the commands from the repository root.

1. **Open the run.** <What to read and apply before deciding anything>.
   Run the command below and keep the returned `run_ref` ([Opening the run]({{creator_rel}}/references/run-evaluation.md#opening-the-run)); from this step on, note each step and each decision with its basis ([Notes of the run]({{creator_rel}}/references/run-evaluation.md#notes-of-the-run)).

   ```powershell
   python -B {{creator_path}}/scripts/run_record.py start --skill {{skill_path}}
   ```

2. **<Step name>.** <What to do, when it is done, and the section that owns the rule the step applies>.
3. **Self-verify.** <The check of the output against the request that the agent can perform; what is fixed before reporting>.
4. **Evaluate and record.** Have the run evaluated ([Evaluating the run]({{creator_rel}}/references/run-evaluation.md#evaluating-the-run)) and its issues improved ([Applying an improvement]({{creator_rel}}/references/run-evaluation.md#applying-an-improvement)), then write exactly one record ([Record]({{creator_rel}}/references/run-evaluation.md#record)):

   ```powershell
   python -B {{creator_path}}/scripts/run_record.py append --input <JSON file>
   ```

5. **Clean up.** <What the run created temporarily and removes>.
6. **Report.** <What changed, how it was verified and what remains open>, then the evaluation of the run ([Reporting]({{creator_rel}}/references/run-evaluation.md#reporting)).
