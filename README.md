# skills-generator

A skill that creates other skills, in one standard format: a folder whose `SKILL.md` says when the skill applies and gives a numbered procedure, with a template, a format reference and a helper script when each run of the skill produces a file of a fixed form.
The format is drawn from the skills of the PIRL framework and stands on its own: `skills-generator` depends on no framework, and a skill it creates carries the rules of its own work.

Every skill it creates is registered in the repository's `AGENTS.md` or `CLAUDE.md`, whichever the repository has; when it has neither, `AGENTS.md` is created.

Every skill it creates also improves from its own runs: each run records the decisions it made and how each step went as one JSON line, the record is evaluated for wrong decisions and wrongly carried out steps, and each issue whose cause lies in a skill is fixed in the file that owns the cause.

## What the repository holds

```text
.skills/skills-generator/
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

1. Install it from the root of the repository:

   ```powershell
   npx skills-generator
   ```

   It copies the skill into `.skills/skills-generator/` and registers it in `AGENTS.md` or `CLAUDE.md`, creating `AGENTS.md` when the repository has neither.
   `--skills-dir <dir>` installs it in another skills directory, and `--create CLAUDE.md` creates `CLAUDE.md` instead.
2. Commit `.skills/` and the instruction file with the repository.
3. Ask the agent for a skill in your own words, for example "create a skill that writes release notes".
   The agent finds `skills-generator` through the instruction file and follows its [`SKILL.md`](.skills/skills-generator/SKILL.md).

The installer needs Node 18 or later; the skill's scripts need Python 3.9 or later and nothing outside the standard library.
Without Node, copy the folder `.skills/skills-generator/` into the repository and run `python -B .skills/skills-generator/scripts/register_skills.py` from its root.

### Updating

Run the same command again, with `@latest` so that `npx` does not reuse the version it cached:

```powershell
npx skills-generator@latest
```

When the skill is already installed, the run updates it instead of installing it.
The evaluation of each run may improve the files of `skills-generator` in the repository, so the update replaces only the files that are still as the last install wrote them.
When a file changed in the repository, it lists the file and changes nothing: merge it by hand, or run again with `--force` to replace it, after committing to keep a copy.
The install writes `.skills/skills-generator/.install.json`, the hashes the update compares with; commit it with the skill.

## The scripts on their own

```powershell
python -B .skills/skills-generator/scripts/new_skill.py --name <name> --size <thin|full> [--artifact <artifact>] [--skills-dir <dir>]
python -B .skills/skills-generator/scripts/register_skills.py [--skills-dir <dir>] [--create <AGENTS.md|CLAUDE.md>] [--check]
python -B .skills/skills-generator/scripts/validate_skill.py --path <skill folder or skills directory> [--skip-registration]
python -B .skills/skills-generator/scripts/run_record.py start --skill <skill folder>
python -B .skills/skills-generator/scripts/run_record.py append --input <JSON file>
python -B .skills/skills-generator/scripts/run_record.py check [--skills-dir <dir>]
python -B .skills/skills-generator/scripts/run_record.py query [--skill <name>] [--issue-key <key>] [--rule <file#section>] [--last <N>] [--all]
```

Each script prints one JSON object with `passed`, and exits with 0 when it is true.
The validator checks structure only; the wording of a skill is re-read against the three scenarios of the [writing rules](.skills/skills-generator/references/writing-rules.md#re-reading-against-three-scenarios).

## Working on this repository

Start from [`AGENTS.md`](AGENTS.md) and run the tests from the repository root:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
node --test tests/installer.test.mjs
```

## Continuous integration and releases

- [`ci.yml`](.github/workflows/ci.yml) runs the Python tests on Python 3.9 and 3.13 and the installer tests on Node 18, 22 and 24, on every push and pull request.
- [`publish.yml`](.github/workflows/publish.yml) publishes `skills-generator` to npm when a tag `v<major>.<minor>.<patch>` is pushed.
  It runs the CI first, then checks that the tag equals the `version` of `package.json`, that this version equals the `metadata.version` of `SKILL.md`, that the tagged commit is on `main` and that the version is not on npm yet.

To release, bump the version in both `package.json` and `.skills/skills-generator/SKILL.md`, merge to `main`, then tag that commit:

```powershell
git tag v<version>
git push origin v<version>
```

The publish job runs in the GitHub environment `npm`, which GitHub creates on the first run; protection rules, such as a required reviewer, are added there.
It authenticates in one of two ways:

1. **First release: a token.** Create a granular access token on npmjs.com with permission to publish, and save it as the secret `NPM_TOKEN` of the repository or of the environment `npm`.
2. **Later releases: trusted publishing.** Once the package exists, open its settings on npmjs.com and add a trusted publisher: GitHub Actions, repository `tdmadc107/skills-creator`, workflow `publish.yml`, environment `npm`.
   npm then authenticates the workflow through OIDC, and the secret `NPM_TOKEN` can be deleted and the token revoked.

npm adds provenance to a package only when its source repository is public; this repository is private, so the workflow publishes without it.

## Protecting the repository

On a public repository nobody but the owner and the collaborators the owner adds can push, create a branch or create a tag; anyone else can only fork it and open a pull request.
The rulesets in [`.github/rulesets/`](.github/rulesets/) protect the repository from mistakes and from collaborators as well, and keep the release tags, which publish to npm, to the owner.
They are imported once in **Settings → Rules → Rulesets → New ruleset → Import a ruleset**, one file at a time; rulesets are enforced on public repositories, and on private ones only with a paid plan.

| Ruleset | Effect |
| --- | --- |
| [`protect-main.json`](.github/rulesets/protect-main.json) | `main` cannot be deleted or force-pushed; every change reaches it through a pull request approved by the code owner ([`CODEOWNERS`](.github/CODEOWNERS)), with every CI job passing on the latest commit |
| [`protect-release-tags.json`](.github/rulesets/protect-release-tags.json) | Only the owner can create, move or delete a tag `v*`, so only the owner can start a release |
| [`restrict-branch-creation.json`](.github/rulesets/restrict-branch-creation.json) | Only the owner can create a branch; a collaborator works from a fork |

Each ruleset lets the repository admins bypass it, so the owner can still merge their own pull request, which no one else can approve, and push release tags.
The checks that `protect-main.json` requires are the job names of [`ci.yml`](.github/workflows/ci.yml), and a test fails while the two differ.

Also set, under **Settings**:

- **Actions → General → Fork pull request workflows from outside collaborators:** require approval for all outside collaborators, so a stranger's pull request runs no workflow until the owner approves it.
- **Actions → General → Workflow permissions:** read repository contents and packages permissions.
- **Environments → npm:** add the owner as a required reviewer, and limit deployment to the tags `v*`, so a release waits for the owner's approval.
