# Maintaining skills-generator

How this repository tests, releases and protects the `skills-generator` package.
Start from [`AGENTS.md`](AGENTS.md) for the rules that apply to every change, and from the [README](README.md) for what the package does.

## Tests

Run them from the repository root:

```powershell
python -B -m unittest discover -s tests -p "test_*.py"
node --test tests/installer.test.mjs
```

The first command tests the skill and its scripts; the second tests the npm installer and the contents of the package.

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

- **Actions → General → Approval for running fork pull request workflows from contributors:** require approval for all external contributors, so the pull request of anyone outside the repository runs no workflow until the owner approves it.
  Leave **Require actions to be pinned to a full-length commit SHA** unchecked: the workflows name actions by version tag, such as `actions/checkout@v6`.
- **Actions → General → Workflow permissions:** read repository contents and packages permissions.
- **Environments → npm:** add the owner as a required reviewer, and limit deployment to the tags `v*`, so a release waits for the owner's approval.
