#!/usr/bin/env node
// Installs skills-generator into the skills folder of every agent provider a project uses, and updates every copy.

import { spawnSync } from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SOURCE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PACKAGE = JSON.parse(fs.readFileSync(path.join(SOURCE, "package.json"), "utf8"));
const SKILL = "skills-generator";
// The paths the packaged skill names to itself start with this folder; each copy gets its own folder instead.
const SOURCE_DIR = ".agents/skills";
const SKILL_SOURCE = path.join(SOURCE, ...SOURCE_DIR.split("/"), SKILL);
// Same table as PROVIDERS in the skill's scripts/_common.py; a test keeps the two equal.
const PROVIDERS = [
  { id: "agents", label: "Codex CLI, Antigravity and other agents that read .agents/", skills: ".agents/skills", detect: [".agents", ".codex", ".agent"] },
  { id: "claude", label: "Claude Code", skills: ".claude/skills", detect: [".claude", "CLAUDE.md"] },
  { id: "cursor", label: "Cursor", skills: ".cursor/skills", detect: [".cursor"] },
  { id: "gemini", label: "Gemini CLI", skills: ".gemini/skills", detect: [".gemini", "GEMINI.md"] },
  { id: "copilot", label: "GitHub Copilot", skills: ".github/skills", detect: [".github/copilot-instructions.md", ".github/instructions"] },
];
const DEFAULT_SKILLS_DIR = ".agents/skills";
// Where version 1.0.0 installed the skill; a copy there is reported, never touched.
const LEGACY_DIR = ".skills";
// Hashes of the files as installed, which updates compare with.
const MANIFEST = ".install.json";
const INSTRUCTION_FILES = ["AGENTS.md", "CLAUDE.md"];
const SKIPPED = new Set(["__pycache__", MANIFEST]);

const USAGE = `Usage: npx ${PACKAGE.name} [options]

Run it at the root folder of your project. It finds the agent providers the project uses
(${PROVIDERS.map((provider) => provider.skills.split("/")[0] + "/").join(", ")} and their instruction files) and copies
the skill into the skills folder of each one, creating that skills folder when it is missing; a project that uses
no provider yet gets ${DEFAULT_SKILLS_DIR}/. A later run updates every copy to this version and keeps the files
changed in the project unless --force.

Options:
  --root <dir>          root folder of the project (default: the current directory)
  --create <file>       AGENTS.md or CLAUDE.md: the file to create when the root has neither
                        (default: CLAUDE.md when Claude Code is the only provider in use, otherwise AGENTS.md)
  --force               when updating, also replace the files changed in the project
  --version             print the version of this package
  --help                print this help`;

class UsageError extends Error {}

function parseArgs(argv) {
  const opts = { root: process.cwd(), create: null, force: false };
  const valueOf = (index, flag) => {
    if (index >= argv.length || argv[index].startsWith("--")) throw new UsageError(`${flag} needs a value`);
    return argv[index];
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--help" || arg === "-h") opts.command = "help";
    else if (arg === "--version" || arg === "-v") opts.command = "version";
    else if (arg === "--force") opts.force = true;
    else if (arg === "--root") opts.root = valueOf(++i, arg);
    else if (arg === "--create") opts.create = valueOf(++i, arg);
    else if (arg.startsWith("--")) throw new UsageError(`unknown option ${arg}`);
    else throw new UsageError(`unexpected argument ${arg}; the package takes options only`);
  }
  if (opts.create !== null && !INSTRUCTION_FILES.includes(opts.create)) throw new UsageError(`--create must be one of ${INSTRUCTION_FILES.join(", ")}`);
  opts.root = path.resolve(opts.root);
  return opts;
}

const sha = (data) => crypto.createHash("sha256").update(data).digest("hex");

/** `added`: files about to be created, which count as present. */
function providersInUse(root, added = []) {
  const present = (rel) => added.includes(rel) || fs.existsSync(path.join(root, rel));
  return PROVIDERS.filter((provider) => [...provider.detect, provider.skills].some(present));
}

function skillsDirs(root, added = []) {
  const unique = [...new Set(providersInUse(root, added).map((provider) => provider.skills))];
  return unique.length ? unique : [DEFAULT_SKILLS_DIR];
}

function fileToCreate(opts) {
  if (opts.create) return opts.create;
  const ids = providersInUse(opts.root).map((provider) => provider.id);
  return ids.length === 1 && ids[0] === "claude" ? "CLAUDE.md" : "AGENTS.md";
}

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

function packagedFiles(skillsDir) {
  const own = `${SOURCE_DIR}/${SKILL}`;
  const target = `${skillsDir}/${SKILL}`;
  const files = {};
  for (const rel of filesOf(SKILL_SOURCE)) {
    const text = fs.readFileSync(path.join(SKILL_SOURCE, rel), "utf8");
    files[rel] = Buffer.from(text.split(own).join(target), "utf8");
  }
  if (!/^  id: \S+$/m.test(files["SKILL.md"].toString("utf8"))) throw new Error("the packaged SKILL.md has no metadata id");
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

function register(opts, skillsDir) {
  const script = `${skillsDir}/${SKILL}/scripts/register_skills.py`;
  const args = ["--create", opts.create];
  const later = `run at the root folder of the project:\n  python -B ${script} ${args.join(" ")}`;
  const cmd = python();
  if (!cmd) {
    console.warn(`warning: Python 3.9 or later was not found, so the skill is not registered yet; with Python installed, ${later}`);
    return;
  }
  const result = spawnSync(cmd[0], [...cmd.slice(1), "-B", script, ...args, "--root", opts.root], { cwd: opts.root, encoding: "utf8" });
  let output;
  try {
    output = JSON.parse(result.stdout);
  } catch {
    output = { passed: false, errors: [(result.stderr || result.stdout).trim()] };
  }
  if (!output.passed) {
    console.warn(`warning: the skill is installed but not registered: ${output.errors.join("; ")}\nOnce that is fixed, ${later}`);
    return;
  }
  for (const file of output.files) console.log(`${file.path}: ${file.state}`);
  for (const reason of output.skipped || []) console.warn(`note: not listed in the instruction file: ${reason}`);
}

/** Every provider holds every skill of the format; a skill of another form stays where the user put it. */
function copyMissingSkills(opts, dirs) {
  const sources = new Map();
  for (const dir of dirs) {
    const base = path.join(opts.root, ...dir.split("/"));
    if (!fs.existsSync(base)) continue;
    for (const entry of fs.readdirSync(base, { withFileTypes: true })) {
      if (!entry.isDirectory() || entry.name === SKILL || sources.has(entry.name)) continue;
      const entryPoint = path.join(base, entry.name, "SKILL.md");
      if (!fs.existsSync(entryPoint)) continue;
      const text = fs.readFileSync(entryPoint, "utf8");
      // A skill of the format: `metadata.kind: skill` and a `metadata.id` that is its own path.
      if (/^  kind: skill$/m.test(text) && new RegExp(`^  id: ${`${dir}/${entry.name}`.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`, "m").test(text)) {
        sources.set(entry.name, dir);
      }
    }
  }
  for (const [name, from] of sources) {
    for (const dir of dirs) {
      const target = path.join(opts.root, ...dir.split("/"), name);
      if (dir === from || fs.existsSync(target)) continue;
      const source = path.join(opts.root, ...from.split("/"), name);
      for (const rel of filesOf(source)) {
        const text = fs.readFileSync(path.join(source, rel), "utf8");
        writeFile(path.join(target, rel), text.split(`${from}/${name}`).join(`${dir}/${name}`).split(`${from}/${SKILL}`).join(`${dir}/${SKILL}`));
      }
      console.log(`Copied ${name} from ${from}/ to ${dir}/`);
    }
  }
}

function planFolder(opts, skillsDir) {
  const folder = path.join(opts.root, ...skillsDir.split("/"), SKILL);
  const files = packagedFiles(skillsDir);
  const manifest = readManifest(folder);
  if (!manifest) {
    if (fs.existsSync(folder)) throw new Error(`${skillsDir}/${SKILL} exists but was not installed by ${PACKAGE.name}; move it away, then run again`);
    return { skillsDir, folder, files, manifest, installed: [], changed: [], blocking: [] };
  }
  const installed = filesOf(folder);
  // A file is changed in the project when it differs from what the last install wrote, or was added there.
  const changed = installed.filter((rel) => manifest.files[rel] !== sha(fs.readFileSync(path.join(folder, rel))));
  const blocking = changed.filter((rel) => !(rel in files) || files[rel].compare(fs.readFileSync(path.join(folder, rel))) !== 0);
  return { skillsDir, folder, files, manifest, installed, changed, blocking };
}

function applyFolder(opts, plan) {
  let written = 0;
  let removed = 0;
  for (const [rel, data] of Object.entries(plan.files)) {
    const target = path.join(plan.folder, rel);
    if (fs.existsSync(target) && data.compare(fs.readFileSync(target)) === 0) continue;
    writeFile(target, data);
    written++;
  }
  for (const rel of plan.installed) {
    if (rel in plan.files || (plan.changed.includes(rel) && !opts.force)) continue;
    fs.rmSync(path.join(plan.folder, rel));
    removed++;
  }
  writeManifest(plan.folder, plan.files);
  const where = `${plan.skillsDir}/${SKILL}/`;
  if (plan.manifest) console.log(`Updated ${where} from ${plan.manifest.version} to ${PACKAGE.version}: ${written} file(s) written, ${removed} removed.`);
  else console.log(`Installed ${SKILL} ${PACKAGE.version} in ${where}`);
}

/** When one copy is blocked, nothing changes anywhere. */
function installOrUpdate(opts) {
  // Decided before installing: the new skills folders would make their providers look in use, and a CLAUDE.md
  // about to be created puts Claude Code in use.
  opts.create = fileToCreate(opts);
  const created = INSTRUCTION_FILES.some((name) => fs.existsSync(path.join(opts.root, name))) ? [] : [opts.create];
  const plans = skillsDirs(opts.root, created).map((skillsDir) => planFolder(opts, skillsDir));
  const blocked = plans.filter((plan) => plan.blocking.length);
  if (blocked.length && !opts.force) {
    throw new Error(`these files changed in the project and differ from version ${PACKAGE.version}:\n`
      + blocked.flatMap((plan) => plan.blocking.map((rel) => `  ${plan.skillsDir}/${SKILL}/${rel}`)).join("\n")
      + "\nmerge them by hand in every copy, or run again with --force to replace them (commit first to keep a copy); nothing was changed");
  }
  for (const plan of plans) applyFolder(opts, plan);
  copyMissingSkills(opts, plans.map((plan) => plan.skillsDir));
  const legacy = path.join(opts.root, LEGACY_DIR, SKILL, MANIFEST);
  if (fs.existsSync(legacy)) {
    console.warn(`warning: ${LEGACY_DIR}/${SKILL}/ holds a copy that version 1.0.0 installed; agents do not read ${LEGACY_DIR}/, so move the skills you created there into the folders above, then delete ${LEGACY_DIR}/`);
  }
  register(opts, plans[0].skillsDir);
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
    if (opts.command === "help") console.log(USAGE);
    else if (opts.command === "version") console.log(PACKAGE.version);
    else installOrUpdate(opts);
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
