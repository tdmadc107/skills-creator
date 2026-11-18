import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CLI = path.join(REPO, "bin", "skills-generator.mjs");
const PACKAGE = JSON.parse(fs.readFileSync(path.join(REPO, "package.json"), "utf8"));
const SKILL_MD = path.join(REPO, ".agents", "skills", "skills-generator", "SKILL.md");
const PYTHON = ["python3", "python"].find((cmd) => spawnSync(cmd, ["--version"]).status === 0);
const GIT = spawnSync("git", ["--version"]).status === 0;

function tempRepo(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skills-generator-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function cli(root, ...args) {
  const result = spawnSync(process.execPath, [CLI, ...args, "--root", root], { encoding: "utf8" });
  return { code: result.status, out: result.stdout, err: result.stderr };
}

function validate(root, skillPath, target = skillPath) {
  const script = path.join(root, skillPath, "scripts", "validate_skill.py");
  const result = spawnSync(PYTHON, ["-B", script, "--path", target, "--root", root], { encoding: "utf8" });
  return JSON.parse(result.stdout);
}

test("the package version is the version of the skill", () => {
  const version = fs.readFileSync(SKILL_MD, "utf8").match(/^  version: (\S+)$/m)[1];
  assert.equal(PACKAGE.version, version);
});

test("the package ships the installer, the skill and nothing else", () => {
  const result = spawnSync("npm", ["pack", "--dry-run", "--json", "--ignore-scripts"], { cwd: REPO, encoding: "utf8", shell: process.platform === "win32" });
  assert.equal(result.status, 0, result.stderr);
  const packed = JSON.parse(result.stdout)[0].files.map((file) => file.path).sort();
  const tracked = spawnSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "--", ".agents/skills/skills-generator", "bin"], { cwd: REPO, encoding: "utf8" });
  assert.equal(tracked.status, 0, tracked.stderr);
  const expected = [...tracked.stdout.split("\n").filter(Boolean), "CHANGELOG.md", "LICENSE", "README.md", "package.json"].sort();
  assert.deepEqual(packed, expected);
});

test("a project with no provider gets .agents/skills and AGENTS.md, and the installed skill passes its validator", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const first = cli(root);
  assert.equal(first.code, 0, first.err);
  assert.match(first.out, /Installed skills-generator .* in \.agents\/skills\/skills-generator\//);
  assert.match(first.out, /AGENTS\.md: created/);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, ".agents/skills/skills-generator/.install.json"), "utf8"));
  assert.equal(manifest.version, PACKAGE.version);
  assert.ok("SKILL.md" in manifest.files && "scripts/run_record.py" in manifest.files);
  assert.ok(!Object.keys(manifest.files).some((rel) => rel.includes("__pycache__")));
  assert.match(fs.readFileSync(path.join(root, "AGENTS.md"), "utf8"), /\| \[`skills-generator`\]\(\.agents\/skills\/skills-generator\/SKILL\.md\) \|/);
  assert.deepEqual(validate(root, ".agents/skills/skills-generator"), { passed: true, path: ".agents/skills/skills-generator" });

  const again = cli(root);
  assert.equal(again.code, 0, again.err);
  assert.match(again.out, /Updated \.agents\/skills\/skills-generator\/ from .* 0 file\(s\) written, 0 removed/);
  assert.deepEqual(fs.readdirSync(root).sort(), [".agents", "AGENTS.md"]);
});

function validateFolder(root, dir) {
  return validate(root, `${dir}/skills-generator`, dir);
}

function installedDirs(root) {
  return [".agents/skills", ".claude/skills", ".cursor/skills", ".gemini/skills", ".github/skills"]
    .filter((dir) => fs.existsSync(path.join(root, dir, "skills-generator", ".install.json")));
}

test("each provider in use gets a full copy in its skills folder, with its own paths", { skip: !PYTHON && "Python is required" }, (t) => {
  const cases = [
    { setup: [".claude/"], dirs: [".claude/skills"], file: "CLAUDE.md" },
    { setup: ["CLAUDE.md"], dirs: [".claude/skills"], file: "CLAUDE.md" },
    { setup: [".claude/skills/my-skill/"], dirs: [".claude/skills"], file: "CLAUDE.md" },
    { setup: [".claude/", ".codex/"], dirs: [".agents/skills", ".claude/skills"], file: "AGENTS.md" },
    { setup: [".cursor/", ".gemini/", ".github/workflows/"], dirs: [".cursor/skills", ".gemini/skills"], file: "AGENTS.md" },
    { setup: [".github/copilot-instructions.md"], dirs: [".github/skills"], file: "AGENTS.md" },
  ];
  for (const { setup, dirs, file } of cases) {
    const root = tempRepo(t);
    for (const entry of setup) {
      if (entry.endsWith("/")) fs.mkdirSync(path.join(root, entry), { recursive: true });
      else {
        fs.mkdirSync(path.dirname(path.join(root, entry)), { recursive: true });
        fs.writeFileSync(path.join(root, entry), "# Mine\n");
      }
    }
    const result = cli(root);
    assert.equal(result.code, 0, `${setup}: ${result.err}`);
    assert.deepEqual(installedDirs(root), dirs, setup.join(", "));
    assert.ok(!fs.existsSync(path.join(root, ".skills")), "no .skills folder is created");
    assert.match(fs.readFileSync(path.join(root, file), "utf8"), /<!-- skills:start -->/, setup.join(", "));
    for (const dir of dirs) {
      const text = fs.readFileSync(path.join(root, dir, "skills-generator", "SKILL.md"), "utf8");
      assert.match(text, new RegExp(`^  id: ${dir.replace(/[./]/g, "\\$&")}/skills-generator$`, "m"));
      assert.match(text, new RegExp(`python -B ${dir.replace(/[./]/g, "\\$&")}/skills-generator/scripts/run_record\\.py start`));
      assert.deepEqual(validateFolder(root, dir), { passed: true, path: dir }, `${setup}: ${dir}`);
    }
  }
});

test("a provider added later gets every skill of the format, and a skill of another form stays where it is", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const own = path.join(root, ".claude/skills/my-review");
  fs.mkdirSync(own, { recursive: true });
  fs.writeFileSync(path.join(own, "SKILL.md"), "---\nname: my-review\ndescription: >\n  Reviews a pull request.\n  Use when asked.\n---\n\n# Review\n");
  assert.equal(cli(root).code, 0);
  const creator = path.join(root, ".claude/skills/skills-generator/scripts/new_skill.py");
  const made = spawnSync(PYTHON, ["-B", creator, "--name", "release-notes", "--size", "thin", "--root", root], { encoding: "utf8" });
  assert.equal(made.status, 0, made.stdout);
  const entry = path.join(root, ".claude/skills/release-notes/SKILL.md");
  fs.writeFileSync(entry, fs.readFileSync(entry, "utf8").replace(/<[^<>\n]+>/g, "filled"));

  fs.mkdirSync(path.join(root, ".cursor"));
  const result = cli(root);
  assert.equal(result.code, 0, result.err);
  assert.match(result.out, /Copied release-notes from \.claude\/skills\/ to \.cursor\/skills\//);
  assert.deepEqual(fs.readdirSync(path.join(root, ".cursor/skills")).sort(), ["release-notes", "skills-generator"]);
  assert.match(fs.readFileSync(path.join(root, ".cursor/skills/release-notes/SKILL.md"), "utf8"), /^  id: \.cursor\/skills\/release-notes$/m);
  assert.match(fs.readFileSync(path.join(root, "CLAUDE.md"), "utf8"), /\| \[`my-review`\]\(\.claude\/skills\/my-review\/SKILL\.md\) \| Reviews a pull request\. Use when asked\. \|/);
  assert.equal(validate(root, ".claude/skills/skills-generator", ".claude/skills/release-notes").passed, true);
  assert.doesNotMatch(cli(root).out, /Copied/);
});

test("a Windows checkout with CRLF line endings does not count as a change", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  assert.equal(cli(root).code, 0);
  const folder = path.join(root, ".agents/skills/skills-generator");
  for (const rel of ["SKILL.md", "references/skill-format.md", "scripts/_common.py"]) {
    const file = path.join(folder, rel);
    fs.writeFileSync(file, fs.readFileSync(file, "utf8").replace(/\n/g, "\r\n"));
  }
  const again = cli(root);
  assert.equal(again.code, 0, again.err);
  assert.match(again.out, /0 file\(s\) written, 0 removed/);
  assert.equal(validate(root, ".agents/skills/skills-generator").passed, true);
});

test("a run from a subfolder of a Git repository stops and names the root, unless --root is given", { skip: !GIT && "Git is required" }, (t) => {
  const root = tempRepo(t);
  assert.equal(spawnSync("git", ["init", "-q"], { cwd: root }).status, 0);
  const sub = path.join(root, "src", "app");
  fs.mkdirSync(sub, { recursive: true });
  const result = spawnSync(process.execPath, [CLI], { cwd: sub, encoding: "utf8" });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /is not the root folder of the project; run the command in /);
  assert.deepEqual(fs.readdirSync(sub), []);
  assert.ok(!fs.existsSync(path.join(root, ".agents")));
  const named = spawnSync(process.execPath, [CLI, "--root", sub], { cwd: sub, encoding: "utf8" });
  assert.equal(named.status, 0, named.stderr);
});

test("--create CLAUDE.md in a project with no provider installs for Claude Code", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const result = cli(root, "--create", "CLAUDE.md");
  assert.equal(result.code, 0, result.err);
  assert.deepEqual(installedDirs(root), [".claude/skills"]);
  assert.ok(!fs.existsSync(path.join(root, "AGENTS.md")));
  assert.equal(validateFolder(root, ".claude/skills").passed, true);
});

test("a copy installed by version 1.0.0 in .skills is reported and left alone", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const legacy = path.join(root, ".skills/skills-generator");
  fs.mkdirSync(legacy, { recursive: true });
  fs.writeFileSync(path.join(legacy, ".install.json"), JSON.stringify({ package: "skills-generator", version: "1.0.0", files: {} }));
  const result = cli(root);
  assert.equal(result.code, 0, result.err);
  assert.match(result.err, /\.skills\/skills-generator\/ holds a copy that version 1\.0\.0 installed/);
  assert.ok(fs.existsSync(path.join(legacy, ".install.json")));
  assert.deepEqual(installedDirs(root), [".agents/skills"]);
});

test("the first run keeps an existing instruction file and refuses a folder it did not install", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  fs.writeFileSync(path.join(root, "CLAUDE.md"), "# Project\n\nRules.\n");
  assert.equal(cli(root).code, 0);
  assert.ok(fs.readFileSync(path.join(root, "CLAUDE.md"), "utf8").startsWith("# Project\n\nRules.\n\n<!-- skills:start -->"));
  assert.deepEqual(installedDirs(root), [".claude/skills"]);

  const other = tempRepo(t);
  fs.mkdirSync(path.join(other, ".agents/skills/skills-generator"), { recursive: true });
  const result = cli(other);
  assert.equal(result.code, 1);
  assert.match(result.err, /exists but was not installed by skills-generator; move it away/);
});

test("a later run keeps the files changed in the repository unless --force", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  assert.equal(cli(root).code, 0);
  const folder = path.join(root, ".agents/skills/skills-generator");
  const manifestFile = path.join(folder, ".install.json");

  const unchanged = cli(root);
  assert.equal(unchanged.code, 0, unchanged.err);
  assert.match(unchanged.out, /0 file\(s\) written, 0 removed/);

  const writing = path.join(folder, "references/writing-rules.md");
  fs.appendFileSync(writing, "\nA local improvement.\n");
  const blocked = cli(root);
  assert.equal(blocked.code, 1);
  assert.match(blocked.err, /references\/writing-rules\.md/);
  assert.match(fs.readFileSync(writing, "utf8"), /A local improvement\./);

  // A file an older version installed and this one no longer ships is removed when unchanged.
  const old = path.join(folder, "references/old.md");
  fs.writeFileSync(old, "old\n");
  const manifest = JSON.parse(fs.readFileSync(manifestFile, "utf8"));
  manifest.files["references/old.md"] = "5b4b2d6e9a0b8e0cfa4e10c5f7d9bd9ccc0e9f5dc2a1a4c2e9c1b0b0d6e7c2a1";
  fs.writeFileSync(manifestFile, JSON.stringify(manifest));
  assert.equal(cli(root).code, 1);
  assert.ok(fs.existsSync(old), "a file whose content differs from the manifest counts as changed");

  const forced = cli(root, "--force");
  assert.equal(forced.code, 0, forced.err);
  assert.doesNotMatch(fs.readFileSync(writing, "utf8"), /A local improvement\./);
  assert.ok(!fs.existsSync(old));
  assert.equal(validate(root, ".agents/skills/skills-generator").passed, true);
});

test("bad arguments print the usage and change nothing", (t) => {
  const root = tempRepo(t);
  for (const args of [["--create", "README.md"], ["--skills-dir", path.join(root, "abs")], ["init"], ["update"], ["--bogus"], ["--root"]]) {
    const result = cli(root, ...args);
    assert.equal(result.code, 2, `${args.join(" ")}: ${result.err}`);
    assert.match(result.err, /Usage: npx skills-generator/);
  }
  assert.deepEqual(fs.readdirSync(root), []);
  assert.equal(cli(root, "--version").out.trim(), PACKAGE.version);
  assert.match(cli(root, "--help").out, /^Usage: npx skills-generator \[options\]/);
});
