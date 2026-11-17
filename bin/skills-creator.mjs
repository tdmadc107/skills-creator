#!/usr/bin/env node
// Installs the skills-creator skill into a repository, registers it in AGENTS.md or CLAUDE.md, and updates it later
// without overwriting the improvements that the evaluation of its runs made in that repository. Needs only Node;
// the registration runs the skill's own Python script, which needs Python 3.9 or later.

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PACKAGE = JSON.parse(fs.readFileSync(path.join(SOURCE, "package.json"), "utf8"));
const SKILL = "skills-creator";
const SKILL_SOURCE = path.join(SOURCE, ".skills", SKILL);
// Written into the installed skill folder: the package, its version and the hash of every file as installed.
const MANIFEST = ".install.json";
const INSTRUCTION_FILES = ["AGENTS.md", "CLAUDE.md"];
const SKIPPED = new Set(["__pycache__", MANIFEST]);

const USAGE = `Usage: npx ${PACKAGE.name} <command> [options]

Commands:
  init      copy the skill into <skills-dir>/${SKILL}/ and register it
  update    replace the installed skill with this version; files changed in the repository are kept unless --force
  version   print the version of this package

Options:
  --root <dir>          root of the repository (default: the current directory)
  --skills-dir <dir>    directory that holds the skills, relative to the root (default: .skills)
  --create <file>       AGENTS.md or CLAUDE.md: the file to create when the root has neither (default: AGENTS.md)
  --force               update: also replace the files changed in the repository
  --help                print this help`;

class UsageError extends Error {}

function parseArgs(argv) {
  const opts = { root: process.cwd(), skillsDir: ".skills", create: "AGENTS.md", force: false };
  const valueOf = (index, flag) => {
    if (index >= argv.length || argv[index].startsWith("--")) throw new UsageError(`${flag} needs a value`);
    return argv[index];
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") opts.command = "help";
    else if (arg === "--force") opts.force = true;
    else if (arg === "--root") opts.root = valueOf(++i, arg);
    else if (arg === "--skills-dir") opts.skillsDir = valueOf(++i, arg);
    else if (arg === "--create") opts.create = valueOf(++i, arg);
    else if (arg.startsWith("--")) throw new UsageError(`unknown option ${arg}`);
    else if (!opts.command) opts.command = arg;
    else throw new UsageError(`unexpected argument ${arg}`);
  }
  if (!INSTRUCTION_FILES.includes(opts.create)) throw new UsageError(`--create must be one of ${INSTRUCTION_FILES.join(", ")}`);
  if (path.isAbsolute(opts.skillsDir)) throw new UsageError("--skills-dir must be relative to the root, because the skill names its own path from there");
  opts.root = path.resolve(opts.root);
  opts.skillsDir = opts.skillsDir.split(path.sep).join("/").replace(/\/+$/, "");
  return opts;
}

const sha = (data) => crypto.createHash("sha256").update(data).digest("hex");

/** Every file of a skill folder, as posix paths relative to it, without caches and the manifest. */
function filesOf(folder) {
  const out = [];
  const walk = (rel) => {
    for (const entry of fs.readdirSync(path.join(folder, rel), { withFileTypes: true })) {
      if (SKIPPED.has(entry.name)) continue;
      const child = rel ? `${rel}/${entry.name}` : entry.name;
      if (entry.isDirectory()) walk(child);
      else if (entry.isFile()) out.push(child);
    }
  };
  walk("");
  return out.sort();
}

/** The package's files as they are written into the repository: SKILL.md carries the path the skill lives at. */
function packagedFiles(skillsDir) {
  const files = {};
  for (const rel of filesOf(SKILL_SOURCE)) {
    let data = fs.readFileSync(path.join(SKILL_SOURCE, rel));
    if (rel === "SKILL.md") {
      const text = data.toString("utf8");
      const id = `  id: ${skillsDir}/${SKILL}`;
      if (!/^  id: .*$/m.test(text)) throw new Error("the packaged SKILL.md has no metadata id");
      data = Buffer.from(text.replace(/^  id: .*$/m, id), "utf8");
    }
    files[rel] = data;
  }
  return files;
}

function writeFile(file, data) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, data);
}

function writeManifest(folder, files) {
  const manifest = { package: PACKAGE.name, version: PACKAGE.version, files: {} };
  for (const [rel, data] of Object.entries(files)) manifest.files[rel] = sha(data);
  writeFile(path.join(folder, MANIFEST), `${JSON.stringify(manifest, null, 2)}\n`);
}

function readManifest(folder) {
  const file = path.join(folder, MANIFEST);
  if (!fs.existsSync(file)) return null;
  const manifest = JSON.parse(fs.readFileSync(file, "utf8"));
  if (manifest.package !== PACKAGE.name || typeof manifest.files !== "object") throw new Error(`${file} was not written by ${PACKAGE.name}`);
  return manifest;
}

function python() {
  for (const cmd of [["python3"], ["python"], ["py", "-3"]]) {
    const result = spawnSync(cmd[0], [...cmd.slice(1), "--version"], { encoding: "utf8" });
    const match = `${result.stdout || ""}${result.stderr || ""}`.match(/Python (\d+)\.(\d+)/);
    if (result.status === 0 && match && (Number(match[1]) > 3 || (Number(match[1]) === 3 && Number(match[2]) >= 9))) return cmd;
  }
  return null;
}

/** Run the skill's own registration; without Python, say which command registers the skill later. */
function register(opts) {
  const script = `${opts.skillsDir}/${SKILL}/scripts/register_skills.py`;
  const args = ["--skills-dir", opts.skillsDir, "--create", opts.create];
  const cmd = python();
  if (!cmd) {
    console.warn(`warning: Python 3.9 or later was not found, so the skill is not registered yet; with Python installed, run:\n  python -B ${script} ${args.join(" ")}`);
    return false;
  }
  const result = spawnSync(cmd[0], [...cmd.slice(1), "-B", script, ...args, "--root", opts.root], { cwd: opts.root, encoding: "utf8" });
  let output;
  try {
    output = JSON.parse(result.stdout);
  } catch {
    throw new Error(`the registration did not run: ${(result.stderr || result.stdout).trim()}`);
  }
  if (!output.passed) throw new Error(`the registration failed: ${output.errors.join("; ")}`);
  for (const file of output.files) console.log(`${file.path}: ${file.state}`);
  return true;
}

function init(opts) {
  const folder = path.join(opts.root, opts.skillsDir, SKILL);
  if (fs.existsSync(folder)) {
    const how = readManifest(folder) ? `run \`npx ${PACKAGE.name} update\`` : "move it away first, because it was not installed by this package";
    throw new Error(`${path.relative(opts.root, folder) || folder} already exists; ${how}`);
  }
  const files = packagedFiles(opts.skillsDir);
  for (const [rel, data] of Object.entries(files)) writeFile(path.join(folder, rel), data);
  writeManifest(folder, files);
  console.log(`Installed ${SKILL} ${PACKAGE.version} in ${opts.skillsDir}/${SKILL}/.`);
  register(opts);
}

function update(opts) {
  const folder = path.join(opts.root, opts.skillsDir, SKILL);
  const manifest = readManifest(folder);
  if (!manifest) throw new Error(`${opts.skillsDir}/${SKILL}/ was not installed by ${PACKAGE.name}; run \`npx ${PACKAGE.name} init\` first`);
  const files = packagedFiles(opts.skillsDir);
  const installed = new Set(filesOf(folder));
  // A file is changed in the repository when it differs from what the last install wrote, or was added there.
  const changed = [...installed].filter((rel) => manifest.files[rel] !== sha(fs.readFileSync(path.join(folder, rel))));
  const blocking = changed.filter((rel) => !(rel in files) || files[rel].compare(fs.readFileSync(path.join(folder, rel))) !== 0);
  if (blocking.length && !opts.force) {
    throw new Error(`these files of ${opts.skillsDir}/${SKILL}/ changed in the repository and differ from version ${PACKAGE.version}:\n`
      + blocking.map((rel) => `  ${rel}`).join("\n")
      + "\nmerge them by hand, or run again with --force to replace them (commit first to keep a copy)");
  }
  let written = 0;
  let removed = 0;
  for (const [rel, data] of Object.entries(files)) {
    const target = path.join(folder, rel);
    if (fs.existsSync(target) && data.compare(fs.readFileSync(target)) === 0) continue;
    writeFile(target, data);
    written++;
  }
  for (const rel of installed) {
    if (rel in files || (changed.includes(rel) && !opts.force)) continue;
    fs.rmSync(path.join(folder, rel));
    removed++;
  }
  writeManifest(folder, files);
  console.log(`Updated ${SKILL} from ${manifest.version} to ${PACKAGE.version}: ${written} file(s) written, ${removed} removed.`);
  register(opts);
}

function main(argv) {
  let opts;
  try {
    opts = parseArgs(argv);
  } catch (error) {
    console.error(`error: ${error.message}\n\n${USAGE}`);
    return 2;
  }
  try {
    if (!opts.command || opts.command === "help") console.log(USAGE);
    else if (opts.command === "version") console.log(PACKAGE.version);
    else if (opts.command === "init") init(opts);
    else if (opts.command === "update") update(opts);
    else throw new UsageError(`unknown command ${opts.command}`);
  } catch (error) {
    if (error instanceof UsageError) {
      console.error(`error: ${error.message}\n\n${USAGE}`);
      return 2;
    }
    console.error(`error: ${error.message}`);
    return 1;
  }
  return 0;
}

process.exitCode = main(process.argv.slice(2));
