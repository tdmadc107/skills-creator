# Agent instructions

This repository is the source of the `skills-creator` skill, which lives in [`.skills/skills-creator/`](.skills/skills-creator/SKILL.md).

- A request to create or adjust a skill, including the skill of this repository, runs through that skill.
- After a change to the skill, to its scripts or to the installer in `bin/`, run the tests from the repository root:

  ```powershell
  python -B -m unittest discover -s tests -p "test_*.py"
  node --test tests/installer.test.mjs
  ```

- The package version and the skill version are one version: a change that bumps `metadata.version` in `SKILL.md` bumps `version` in `package.json` to the same value, and a test fails while they differ.
- A release is published by the [publish workflow](.github/workflows/publish.yml) when the user pushes a tag; create or push a tag only when the user asks for a release, as described in the [README](README.md#continuous-integration-and-releases).

- Commit or push only when the user asks.

<!-- skills:start -->
## Skills

This block is generated from the `SKILL.md` files in `.skills/`: change those files, then register the skills again; do not edit it by hand.

When a request matches the description of a skill below, read that skill's `SKILL.md` in full and follow it; relative paths in that file resolve from its own folder.
When no skill matches, work without one.

| Skill | Description |
| --- | --- |
| [`skills-creator`](.skills/skills-creator/SKILL.md) | Creates or adjusts an agent skill in the standard skill format. Turns a request for a skill into a skill folder whose SKILL.md holds the frontmatter, when the skill applies and a numbered procedure, with a template, a format reference and a helper script when each run of the skill produces a file of a fixed form, then registers every skill in the repository's AGENTS.md or CLAUDE.md, creating that file when the repository has neither, and validates the structure. Every skill it creates records the decisions and the steps of each run, has the record evaluated and is improved from the issues found. Use only when the user's own words ask to create, scaffold, restructure or adjust a skill, or to improve a skill from its run records. Do not use to run an existing skill, to answer a question about skills that only needs an explanation, or to write agent instructions that are not a skill. |
<!-- skills:end -->
