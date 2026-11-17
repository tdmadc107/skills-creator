# Writing rules

The `skills-creator` skill owns how the content of a skill is worded.
How a skill is laid out, named, stored and registered belongs to the [skill format](skill-format.md).

## Description

The `description` is the only part of a skill an agent sees before it decides to open the skill, so it carries the whole decision.
Write it as one line in three parts, in this order:

1. What a run does and what it produces, in one or two sentences that start with a verb.
2. `Use only when ...`: the requests that open the skill, stated by what the user's own words ask for.
3. `Do not use ...`: the nearby requests the skill must not take, each of them work that another skill or a direct answer owns.

Name the requests by kind of situation, not by keywords: a description that lists trigger words opens the skill on a mention and misses the same request in other words.
Two skills of one skills directory never take the same request; when a new skill overlaps an existing one, settle the boundary and state it in both descriptions.

## One owner per rule

Each rule lives in exactly one file, and every other file points to it instead of copying it.

- Before writing a rule, look for the document that already owns it: the repository's instruction file, its contributing or architecture documentation, another skill.
  When one exists, the step links to that section and states only what the step adds.
- When no document owns it, the skill owns it: in the format reference when the rule is about the artifact of a full skill, otherwise in the step itself.
- `SKILL.md` owns when the skill applies and the order of the steps.
  The format reference owns how the artifact is laid out, named and stored.
  A script owns nothing: its docstring names the reference whose rules it applies.
- A skill does not restate the description in its body, and a step does not restate the section it links to.

## General form

A skill is written for every run of its kind of work, in any repository where it is installed.

- State conditions by kind of situation and actions by what is done and what it produces, not by one event that happened.
- Keep out of a skill what belongs to one run or one project: product names, paths inside a product repository, task IDs, dates, quotes of the user, values that were right once.
  An example, when one is needed, is marked as an example and never becomes a condition.
- Fix a wrong passage by replacing it with a condition and an action that are concrete enough; do not pile a reminder on top of it.

## Steps

- A step says one thing to do and when it is done; a decision the agent must make names the cases and what each case leads to.
- A step that needs something from the user says what to ask, that the question covers only the missing decisions that change the result, and which parts continue meanwhile.
- A step that can fail says what happens then: fix and rerun, go back to a named step, or stop and report.
- A command is written in full, with the path from the repository root, and its `<...>` values are named after what they hold.
- The verification step names a check the agent can actually perform, and the report step says what changed, how it was verified and what remains open; which steps end a procedure belongs to the [Body](skill-format.md#body) section of the skill format.

## Line layout

- Write the prose without hard wraps: a line ends where a sentence ends, and every sentence starts a new line, however long the line is.
- A `;` or a `:` does not end a line, except a `:` that ends a paragraph or a list item before a list, a table or a code block.
- A sentence ending inside a code span, a link, parentheses, a `<...>` placeholder or bold text does not end the line.
- Frontmatter, headings, tables and code blocks keep their own form.

## Language

Write the files of a skill in English, and keep IDs, data keys, symbols, commands and paths verbatim.
Replies to the user follow the language the user writes in, whatever language the skill is written in.

## Re-reading against three scenarios

A structure check proves nothing about the wording, so the finished skill is re-read against three requests, each followed step by step as an agent that knows only the skill would follow it:

1. A request the skill is made for: the description opens the skill, and every step can be carried out with what the skill and its links give.
2. A nearby request the skill must not take: the description and `When to use` send it elsewhere.
3. The first request in another repository, or another host, of the same kind: the skill applies without a change.

A scenario that fails is fixed in the passage that owns the wrong decision, then the three scenarios are read again.
