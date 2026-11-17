// Tests of the npm installer and of the package contents. Run with: node --test tests/installer.test.mjs
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
const SKILL_MD = path.join(REPO, ".skills", "skills-generator", "SKILL.md");
const PYTHON = ["python3", "python"].find((cmd) => spawnSync(cmd, ["--version"]).status === 0);

function tempRepo(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skills-generator-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}

function cli(root, ...args) {
  const result = spawnSync(process.execPath, [CLI, ...args, "--root", root], { encoding: "utf8" });
  return { code: result.status, out: result.stdout, err: result.stderr };
}

function validate(root, skillPath) {
  const script = path.join(root, skillPath, "scripts", "validate_skill.py");
  const result = spawnSync(PYTHON, ["-B", script, "--path", skillPath, "--root", root], { encoding: "utf8" });
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
  const tracked = spawnSync("git", ["ls-files", "--cached", "--others", "--exclude-standard", "--", ".skills/skills-generator", "bin"], { cwd: REPO, encoding: "utf8" });
  assert.equal(tracked.status, 0, tracked.stderr);
  const expected = [...tracked.stdout.split("\n").filter(Boolean), "LICENSE", "README.md", "package.json"].sort();
  assert.deepEqual(packed, expected);
});

test("the first run installs and registers the skill, and the installed skill passes its validator", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const first = cli(root);
  assert.equal(first.code, 0, first.err);
  assert.match(first.out, /Installed skills-generator /);
  assert.match(first.out, /AGENTS\.md: created/);
  const manifest = JSON.parse(fs.readFileSync(path.join(root, ".skills/skills-generator/.install.json"), "utf8"));
  assert.equal(manifest.version, PACKAGE.version);
  assert.ok("SKILL.md" in manifest.files && "scripts/run_record.py" in manifest.files);
  assert.ok(!Object.keys(manifest.files).some((rel) => rel.includes("__pycache__")));
  assert.match(fs.readFileSync(path.join(root, "AGENTS.md"), "utf8"), /\| \[`skills-generator`\]\(\.skills\/skills-generator\/SKILL\.md\) \|/);
  assert.deepEqual(validate(root, ".skills/skills-generator"), { passed: true, path: ".skills/skills-generator" });

  // A second run updates in place instead of failing.
  const again = cli(root);
  assert.equal(again.code, 0, again.err);
  assert.match(again.out, /Updated skills-generator from .* 0 file\(s\) written, 0 removed/);
});

test("the first run places the skill in the named skills directory and the named instruction file", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  const result = cli(root, "--skills-dir", "tools/skills", "--create", "CLAUDE.md");
  assert.equal(result.code, 0, result.err);
  assert.ok(!fs.existsSync(path.join(root, "AGENTS.md")));
  assert.match(fs.readFileSync(path.join(root, "tools/skills/skills-generator/SKILL.md"), "utf8"), /^  id: tools\/skills\/skills-generator$/m);
  assert.equal(validate(root, "tools/skills/skills-generator").passed, true);
});

test("the first run keeps an existing instruction file and refuses a folder it did not install", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  fs.writeFileSync(path.join(root, "CLAUDE.md"), "# Project\n\nRules.\n");
  assert.equal(cli(root).code, 0);
  assert.ok(fs.readFileSync(path.join(root, "CLAUDE.md"), "utf8").startsWith("# Project\n\nRules.\n\n<!-- skills:start -->"));

  const other = tempRepo(t);
  fs.mkdirSync(path.join(other, ".skills/skills-generator"), { recursive: true });
  const result = cli(other);
  assert.equal(result.code, 1);
  assert.match(result.err, /exists but was not installed by skills-generator; move it away/);
});

test("a later run keeps the files changed in the repository unless --force", { skip: !PYTHON && "Python is required" }, (t) => {
  const root = tempRepo(t);
  assert.equal(cli(root).code, 0);
  const folder = path.join(root, ".skills/skills-generator");
  const manifestFile = path.join(folder, ".install.json");

  const unchanged = cli(root);
  assert.equal(unchanged.code, 0, unchanged.err);
  assert.match(unchanged.out, /0 file\(s\) written, 0 removed/);

  // An improvement made in the repository blocks the update and is left as it is.
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
  assert.equal(validate(root, ".skills/skills-generator").passed, true);
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
