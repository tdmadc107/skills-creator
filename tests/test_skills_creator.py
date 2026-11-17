"""Check the skills-creator skill as a package and run its scripts against temporary repositories."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / ".skills" / "skills-creator"
SCRIPTS = SKILL / "scripts"
PLACEHOLDER = re.compile(r"<(?!!--)[^<>\n]+>")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE = re.compile(r"(?ms)^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$")
GOOD_SKILL = """---
name: {name}
description: "{description}"
metadata:
  id: .skills/{name}
  kind: skill
  version: 1.0.0
---

# Work

Carries out one unit of work.

## When to use

- The user asks for the work.
- Not for other work.

## Resources

| Resource | Use |
| --- | --- |
| [`run_record.py`]({tool}) | Writes the run's record |

## Procedure

1. **Open the task.** Read the inputs.
2. **Report.** Say what changed.
"""


def run(script: str, root: Path, *args: str) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPTS / script), *args, "--root", str(root)],
                            capture_output=True, text=True, encoding="utf-8")
    return result.returncode, json.loads(result.stdout)


def good_skill(root: Path, name: str, description: str) -> str:
    """A minimal skill of the format; it links the real record tool by its path from the skill folder."""

    tool = Path(os.path.relpath(SCRIPTS / "run_record.py", root / ".skills" / name)).as_posix()
    return GOOD_SKILL.format(name=name, description=description, tool=tool)


def fill(folder: Path) -> None:
    """Stand in for the agent: replace every <...> placeholder of the Markdown files of a scaffolded skill."""

    for path in folder.rglob("*.md"):
        path.write_text(PLACEHOLDER.sub("filled", path.read_text(encoding="utf-8")), encoding="utf-8")


class Repository(unittest.TestCase):
    """A temporary repository that receives skills."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def write_skill(self, name: str, text: str | None = None, description: str = "Does the work. Use only when asked. Do not use otherwise.") -> Path:
        folder = self.root / ".skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(text or good_skill(self.root, name, description), encoding="utf-8")
        return folder

    def errors(self, *args: str) -> list[str]:
        return run("validate_skill.py", self.root, *args)[1].get("errors", [])


class PackageTests(unittest.TestCase):
    def test_the_skill_follows_its_own_format_and_is_registered(self):
        code, result = run("validate_skill.py", REPO, "--path", ".skills")
        self.assertEqual(code, 0, result)

    def test_repository_links_resolve(self):
        for source in (REPO / "README.md", REPO / "AGENTS.md"):
            for target in LINK.findall(FENCE.sub("", source.read_text(encoding="utf-8"))):
                if re.match(r"[a-z]+:", target):
                    continue
                with self.subTest(source=source.name, target=target):
                    self.assertTrue((REPO / target.partition("#")[0]).exists())

    def test_scripts_postpone_annotations(self):
        # Postponed annotations keep `X | None` hints valid on Python 3.9, the oldest version the scripts support.
        for script in sorted(SCRIPTS.glob("*.py")) + [SKILL / "assets" / "script-template.py"]:
            with self.subTest(script=script.name):
                self.assertIn("from __future__ import annotations", script.read_text(encoding="utf-8"))


class NewSkillTests(Repository):
    """The scaffolder runs from the copy of skills-creator inside the repository that receives the new skill."""

    def setUp(self):
        super().setUp()
        self.creator = self.root / ".skills" / "skills-creator"
        shutil.copytree(SKILL, self.creator, ignore=shutil.ignore_patterns("__pycache__"))

    def new_skill(self, *args: str) -> tuple[int, dict]:
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(self.creator / "scripts" / "new_skill.py"), *args, "--root", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8")
        return result.returncode, json.loads(result.stdout)

    def test_a_copy_outside_the_repository_refuses(self):
        code, result = run("new_skill.py", self.root, "--name", "report", "--size", "thin")
        self.assertEqual(code, 1)
        self.assertIn("copy it into the repository", result["errors"][0])
        self.assertFalse((self.root / ".skills/report").exists())

    def test_thin_skill_is_scaffolded_filled_and_validated(self):
        code, result = self.new_skill("--name", "release-notes", "--size", "thin")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["files"], [".skills/release-notes/SKILL.md"])
        self.assertTrue(any("placeholder" in error for error in self.errors("--path", result["path"], "--skip-registration")))
        fill(self.root / result["path"])
        self.assertEqual(self.errors("--path", result["path"], "--skip-registration"), [])
        # The scaffolded skill opens its run with the record tool, at the path the template filled in.
        text = (self.root / result["path"] / "SKILL.md").read_text(encoding="utf-8")
        command = re.search(r"python -B (\S+run_record\.py) start --skill (\S+)", text)
        self.assertEqual(command.groups(), (".skills/skills-creator/scripts/run_record.py", ".skills/release-notes"))
        self.assertIn("](../skills-creator/scripts/run_record.py)", text)
        code, opened = run("run_record.py", self.root, "start", "--skill", command.group(2))
        self.assertEqual((code, opened["run_ref"]["skill"], opened["run_ref"]["steps"]), (0, "release-notes", 6), opened)

    def test_full_skill_is_scaffolded_and_its_script_creates_the_artifact(self):
        code, result = self.new_skill("--name", "incident-report", "--size", "full", "--artifact", "post-mortem")
        self.assertEqual(code, 0, result)
        self.assertEqual(sorted(result["files"]), [
            ".skills/incident-report/SKILL.md",
            ".skills/incident-report/assets/post-mortem-template.md",
            ".skills/incident-report/references/post-mortem-format.md",
            ".skills/incident-report/scripts/new_post_mortem.py",
        ])
        folder = self.root / result["path"]
        text = (folder / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("{{", text)
        self.assertIn("python -B .skills/incident-report/scripts/new_post_mortem.py", text)
        fill(folder)
        self.assertEqual(self.errors("--path", result["path"], "--skip-registration"), [])

        script = folder / "scripts" / "new_post_mortem.py"
        made = subprocess.run([sys.executable, "-X", "utf8", "-B", str(script), "--root", str(self.root), "--slug", "db-outage", "--out-dir", "reports"],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(made.returncode, 0, made.stdout)
        artifact = self.root / json.loads(made.stdout)["path"]
        self.assertRegex(artifact.relative_to(self.root).as_posix(), r"^reports/db-outage-\d{8}-\d{6}\.md$")
        written = artifact.read_text(encoding="utf-8")
        self.assertIn("schema: incident-report/v1", written)
        self.assertRegex(written, r'created_at: "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}"')
        bad = subprocess.run([sys.executable, "-B", str(script), "--root", str(self.root), "--slug", "Bad Slug"], capture_output=True, text=True)
        self.assertEqual((bad.returncode, json.loads(bad.stdout)["passed"]), (1, False))

    def test_bad_input_creates_nothing_and_an_existing_skill_is_never_overwritten(self):
        for args in (["--name", "Bad Name", "--size", "thin"], ["--name", "x" * 65, "--size", "thin"],
                     ["--name", "report", "--size", "full"], ["--name", "report", "--size", "full", "--artifact", "Bad Slug"],
                     ["--name", "report", "--size", "thin", "--artifact", "note"]):
            with self.subTest(args=args):
                code, result = self.new_skill(*args)
                self.assertEqual((code, result["passed"]), (1, False))
                self.assertEqual([path.name for path in (self.root / ".skills").iterdir()], ["skills-creator"])
        self.assertEqual(self.new_skill("--name", "report", "--size", "thin")[0], 0)
        before = (self.root / ".skills/report/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(self.new_skill("--name", "report", "--size", "full", "--artifact", "note")[0], 1)
        self.assertEqual((self.root / ".skills/report/SKILL.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / ".skills/report/assets").exists())

    def test_skills_directory_can_be_named(self):
        code, result = self.new_skill("--name", "report", "--size", "thin", "--skills-dir", "tools/skills")
        self.assertEqual(code, 0, result)
        self.assertIn("id: tools/skills/report", (self.root / "tools/skills/report/SKILL.md").read_text(encoding="utf-8"))


class RegistrationTests(Repository):
    def register(self, *args: str) -> dict[str, str]:
        code, result = run("register_skills.py", self.root, *args)
        self.assertEqual(code, 0, result)
        return {item["path"]: item["state"] for item in result["files"]}

    def test_a_repository_without_an_instruction_file_gets_agents_md(self):
        self.write_skill("alpha")
        self.assertEqual(self.register(), {"AGENTS.md": "created"})
        text = (self.root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("| [`alpha`](.skills/alpha/SKILL.md) | Does the work. Use only when asked. Do not use otherwise. |", text)
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_the_user_can_name_the_file_to_create(self):
        self.write_skill("alpha")
        self.assertEqual(self.register("--create", "CLAUDE.md"), {"CLAUDE.md": "created"})
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(self.errors("--path", ".skills/alpha"), [])
        # Once a file exists the rule picks it, whatever file is named.
        self.assertEqual(self.register("--create", "AGENTS.md"), {"CLAUDE.md": "unchanged"})
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_a_claude_md_that_names_a_missing_agents_md_still_carries_the_block(self):
        self.write_skill("alpha")
        (self.root / "CLAUDE.md").write_text("See AGENTS.md of the parent project.\n", encoding="utf-8")
        self.assertEqual(self.register(), {"CLAUDE.md": "updated"})

    def test_the_existing_file_is_used_and_the_rest_of_it_is_kept(self):
        self.write_skill("alpha")
        (self.root / "CLAUDE.md").write_text("# Project\n\nRules of the project.\n", encoding="utf-8")
        self.assertEqual(self.register(), {"CLAUDE.md": "updated"})
        self.assertFalse((self.root / "AGENTS.md").exists())
        text = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Project\n\nRules of the project.\n\n<!-- skills:start -->\n"))
        (self.root / "CLAUDE.md").write_text(text + "\n## After\n\nKept.\n", encoding="utf-8")

        self.write_skill("beta", description="Second | skill.")
        self.assertEqual(self.register(), {"CLAUDE.md": "updated"})
        text = (self.root / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- skills:start -->"), 1)
        self.assertIn("| [`beta`](.skills/beta/SKILL.md) | Second \\| skill. |", text)
        self.assertTrue(text.startswith("# Project\n\nRules of the project.\n") and text.endswith("\n## After\n\nKept.\n"))
        self.assertEqual(self.register(), {"CLAUDE.md": "unchanged"})

        shutil.rmtree(self.root / ".skills/alpha")
        self.assertEqual(self.register(), {"CLAUDE.md": "updated"})
        self.assertNotIn("alpha", (self.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_both_files_are_used_unless_one_loads_the_other(self):
        self.write_skill("alpha")
        (self.root / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Claude\n", encoding="utf-8")
        self.assertEqual(self.register(), {"AGENTS.md": "updated", "CLAUDE.md": "updated"})
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        self.assertEqual(self.register(), {"AGENTS.md": "unchanged"})
        self.assertEqual((self.root / "CLAUDE.md").read_text(encoding="utf-8"), "@AGENTS.md\n")

    def test_line_endings_of_the_file_are_kept(self):
        self.write_skill("alpha")
        (self.root / "AGENTS.md").write_bytes(b"# Agents\r\n\r\nRules.\r\n")
        self.register()
        data = (self.root / "AGENTS.md").read_bytes()
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"))
        self.assertEqual(self.register(), {"AGENTS.md": "unchanged"})

    def test_check_writes_nothing_and_fails_while_the_block_is_missing_or_stale(self):
        self.write_skill("alpha")
        self.assertEqual(run("register_skills.py", self.root, "--check")[0], 1)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertTrue(any("AGENTS.md" in error for error in self.errors("--path", ".skills/alpha")))
        self.register()
        self.assertEqual(run("register_skills.py", self.root, "--check")[0], 0)
        self.assertEqual(self.errors("--path", ".skills/alpha"), [])
        self.write_skill("beta")
        self.assertEqual(run("register_skills.py", self.root, "--check")[0], 1)
        self.assertNotIn("beta", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_nothing_to_register_fails(self):
        self.assertEqual(run("register_skills.py", self.root)[0], 1)
        self.assertFalse((self.root / "AGENTS.md").exists())


class RecordTests(Repository):
    def setUp(self):
        super().setUp()
        self.write_skill("work")
        code, opened = run("run_record.py", self.root, "start", "--skill", ".skills/work")
        self.assertEqual(code, 0, opened)
        self.ref = opened["run_ref"]

    def record(self, **changes) -> dict:
        data = {
            "run_ref": self.ref,
            "request": "Do the work for the order page",
            "outcome": {"status": "completed", "summary": "The work is done."},
            "steps": [{"step": 1, "status": "done", "note": "Read the inputs."}, {"step": 2, "status": "pending", "note": "Will report."}],
            "decisions": [{"id": "DEC-01", "step": 1, "decision": "Read only the order page.", "basis": "The user named the order page."}],
            "evaluation": {"mode": "agent", "result": "clean"},
            "issues": [],
            "fixes": [],
            "supersedes": None,
        }
        data.update(changes)
        return data

    def with_issue(self, **issue) -> dict:
        found = {"id": "ISSUE-01", "issue_key": "inputs-not-listed", "subject": "DEC-01", "cause": "instruction",
                 "problem": "The step does not say which inputs to read.", "rule": ".skills/work/SKILL.md#procedure", "evidence": "Step 1."}
        found.update(issue)
        fix = {"id": "FIX-01", "issues": ["ISSUE-01"], "status": "applied", "files": [{"path": ".skills/work/SKILL.md", "section": "Procedure"}],
               "summary": "Step 1 lists the inputs.", "checks": ["python -B .skills/skills-creator/scripts/validate_skill.py --path .skills/work"]}
        return self.record(evaluation={"mode": "agent", "result": "issues"}, issues=[found], fixes=[fix])

    def append(self, data: dict) -> tuple[int, dict]:
        source = self.root / "record.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        return run("run_record.py", self.root, "append", "--input", str(source))

    def test_start_pins_the_skill_and_writes_nothing(self):
        self.assertEqual((self.ref["skill"], self.ref["path"], self.ref["version"], self.ref["steps"]), ("work", ".skills/work", "1.0.0", 2))
        self.assertRegex(self.ref["digest"], r"^[0-9a-f]{12}$")
        self.assertFalse((self.root / ".skills/.records").exists())
        entry = self.root / ".skills/work/SKILL.md"
        entry.write_text(entry.read_text(encoding="utf-8").replace("Read the inputs.", "Read every input."), encoding="utf-8")
        self.assertNotEqual(run("run_record.py", self.root, "start", "--skill", ".skills/work")[1]["run_ref"]["digest"], self.ref["digest"])
        self.assertEqual(run("run_record.py", self.root, "start", "--skill", ".skills/missing")[0], 1)

    def test_a_record_is_stored_as_one_line_and_kept_out_of_git(self):
        code, first = self.append(self.record())
        self.assertEqual(code, 0, first)
        self.assertRegex(first["path"], r"^\.skills/\.records/work/\d{4}-\d{2}-\d{2}\.jsonl$")
        ignore = self.root / ".skills/.records/.gitignore"
        self.assertEqual(ignore.read_text(encoding="utf-8"), "*\n")
        ignore.write_text("", encoding="utf-8")
        code, second = self.append(self.record(supersedes=first["record_id"]))
        self.assertEqual(code, 0, second)
        self.assertEqual(ignore.read_text(encoding="utf-8"), "")
        lines = (self.root / first["path"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["record_id"] for line in lines], [first["record_id"], second["record_id"]])
        self.assertEqual(json.loads(lines[0])["schema"], "skill-record/v1")
        self.assertEqual(run("run_record.py", self.root, "check")[1], {"passed": True, "records": 2})
        # The records folder is not a skill: registration and validation ignore it.
        self.assertEqual(run("register_skills.py", self.root)[0], 0)
        self.assertEqual(self.errors("--path", ".skills"), [])

    def test_issues_fixes_and_the_earlier_fix_they_name(self):
        code, first = self.append(self.with_issue())
        self.assertEqual(code, 0, first)
        again = self.with_issue(cause="ineffective_fix", prior_fix=f"{first['record_id']}#FIX-01")
        self.assertEqual(self.append(again)[0], 0)
        for prior in ("unknown-record#FIX-01", f"{first['record_id']}#FIX-09"):
            with self.subTest(prior=prior):
                code, result = self.append(self.with_issue(cause="ineffective_fix", prior_fix=prior))
                self.assertEqual(code, 1)
                self.assertTrue(any("prior_fix" in error for error in result["errors"]), result)
        self.assertEqual(self.append(self.record(supersedes="unknown-record"))[0], 1)
        self.assertEqual(run("run_record.py", self.root, "check")[1]["records"], 2)

    def test_each_departure_from_the_record_contract_is_rejected_and_nothing_is_written(self):
        steps = self.record()["steps"]
        pending = self.with_issue()
        pending["fixes"][0].update({"status": "pending_user", "checks": []})
        unfixed = self.with_issue()
        unfixed["fixes"] = []
        cases = {
            "missing fields": {key: value for key, value in self.record().items() if key != "decisions"},
            "unknown fields": self.record(record_id="mine"),
            "run_ref: copy the object": self.record(run_ref={"skill": "work"}),
            "run_ref.digest": self.record(run_ref={**self.ref, "digest": "abc"}),
            "outcome.status": self.record(outcome={"status": "done", "summary": "Done."}),
            "steps: one entry per step": self.record(steps=steps[:1]),
            "steps[2].status": self.record(steps=[steps[0], {**steps[1], "status": "ok"}]),
            "steps[1].note": self.record(steps=[{**steps[0], "note": ""}, steps[1]]),
            "`pending` marks only the steps that follow": self.record(steps=[{**steps[0], "status": "pending"}, steps[1]]),
            "decisions[1].basis": self.record(decisions=[{"id": "DEC-01", "step": 1, "decision": "Chose.", "basis": ""}]),
            "decisions[1].step": self.record(decisions=[{"id": "DEC-01", "step": 3, "decision": "Chose.", "basis": "Rule."}]),
            "DEC-01 is used twice": self.record(decisions=self.record()["decisions"] * 2),
            "evaluation.mode": self.record(evaluation={"mode": "auto", "result": "clean"}),
            "evaluation.result": self.record(evaluation={"mode": "self", "result": "issues"}),
            "issues[1].subject": self.with_issue(subject="DEC-07"),
            "issues[1].cause": self.with_issue(cause="unknown"),
            "issues[1].issue_key": self.with_issue(issue_key="Not Kebab"),
            "issues[1].prior_fix": self.with_issue(cause="ineffective_fix"),
            "only an issue with the cause ineffective_fix": self.with_issue(prior_fix="x#FIX-01"),
            "fixes[1].reason": pending,
            "every issue belongs to at least one fix": unfixed,
        }
        for message, data in cases.items():
            with self.subTest(message=message):
                code, result = self.append(data)
                self.assertEqual(code, 1, result)
                self.assertTrue(any(message in error for error in result["errors"]), result)
        self.assertFalse((self.root / ".skills/.records").exists())
        self.assertEqual(self.append(self.with_issue(subject="STEP-02"))[0], 0)
        pending["fixes"][0]["reason"] = "safety"
        self.assertEqual(self.append(pending)[0], 0)

    def test_query_finds_records_by_skill_key_and_rule(self):
        self.write_skill("other")
        other = run("run_record.py", self.root, "start", "--skill", ".skills/other")[1]["run_ref"]
        clean = self.append(self.record())[1]["record_id"]
        corrected = self.append(self.record(supersedes=clean))[1]["record_id"]
        issue = self.append(self.with_issue())[1]["record_id"]
        self.append(self.record(run_ref=other))

        def ids(*args: str) -> list[str]:
            return [record["record_id"] for record in run("run_record.py", self.root, "query", *args)[1]["records"]]

        self.assertEqual(ids("--skill", "work"), [corrected, issue])
        self.assertEqual(ids("--skill", "work", "--all"), [clean, corrected, issue])
        self.assertEqual(ids("--skill", "work", "--last", "1"), [issue])
        self.assertEqual(ids("--issue-key", "inputs-not-listed"), [issue])
        self.assertEqual(ids("--issue-key", "other-key", "--rule", ".skills/work/SKILL.md#procedure"), [issue])
        self.assertEqual(ids("--issue-key", "other-key"), [])
        self.assertEqual(len(ids()), 3)

    def test_check_reports_a_stored_line_that_was_edited_by_hand(self):
        path = self.root / self.append(self.record())[1]["path"]
        path.write_text(path.read_text(encoding="utf-8") + "not json\n", encoding="utf-8")
        code, result = run("run_record.py", self.root, "check")
        self.assertEqual(code, 1)
        self.assertTrue(any("not valid JSON" in error for error in result["errors"]), result)


class ValidatorTests(Repository):
    def broken(self, change, name: str = "work") -> list[str]:
        """The validator's errors for a good skill after one change to its SKILL.md."""

        folder = self.root / ".skills" / name
        if not folder.exists():
            self.write_skill(name)
        entry = folder / "SKILL.md"
        entry.write_text(change(good_skill(self.root, name, "Does the work.")), encoding="utf-8")
        return self.errors("--path", f".skills/{name}", "--skip-registration")

    def test_a_good_skill_passes(self):
        self.assertEqual(self.broken(lambda text: text), [])

    def test_each_departure_from_the_format_is_reported(self):
        cases = {
            "must equal the folder name": lambda t: t.replace("name: work", "name: other"),
            "kebab-case": lambda t: t.replace("name: work", "name: Work"),
            "the limit is 1024": lambda t: t.replace("Does the work.", "x" * 1025),
            "description still holds a placeholder": lambda t: t.replace("Does the work.", "Does <what>."),
            "quote the value": lambda t: t.replace('"Does the work."', "Does the work: all of it."),
            "metadata.id": lambda t: t.replace("id: .skills/work", "id: skills/work"),
            "metadata.kind": lambda t: t.replace("kind: skill", "kind: procedure"),
            "metadata.version": lambda t: t.replace("version: 1.0.0", "version: 1.0"),
            "exactly one level-one title": lambda t: t.replace("# Work", "# Work\n\n# Again"),
            "what it owns is missing": lambda t: t.replace("Carries out one unit of work.\n", ""),
            "level-two sections": lambda t: t.replace("## When to use", "## Usage"),
            "When to use must list": lambda t: t.replace("- The user asks for the work.\n- Not for other work.\n", "Always.\n"),
            "numbered from 1 without gaps": lambda t: t.replace("2. **Report.**", "3. **Report.**"),
            "name in bold": lambda t: t.replace("2. **Report.** Say", "2. Report: say"),
            "placeholder(s) outside code": lambda t: t.replace("Read the inputs.", "Read <the inputs>."),
            "names a file that does not exist": lambda t: t.replace("Read the inputs.", "Read the [rules](rules.md)."),
            "names a heading that does not exist": lambda t: t.replace("Read the inputs.", "Read [this](#no-such-heading)."),
            "frontmatter block": lambda t: t.replace("---\nname", "name", 1),
            "must link the record tool": lambda t: re.sub(r"\| \[`run_record.py`\].*\n", "", t),
        }
        for message, change in cases.items():
            with self.subTest(message=message):
                errors = self.broken(change)
                self.assertTrue(any(message in error for error in errors), errors)

    def test_placeholders_in_code_and_links_to_headings_are_accepted(self):
        change = lambda t: t.replace("Read the inputs.", "Run `tool --name <name>` per [When to use](#when-to-use) and see <https://example.com>.")  # noqa: E731
        self.assertEqual(self.broken(change), [])

    def test_resources_need_their_section_their_rows_and_their_content(self):
        folder = self.write_skill("work")
        (folder / "assets").mkdir()
        self.assertTrue(any("assets/ is empty" in error for error in self.broken(lambda t: t)))
        (folder / "assets/note-template.md").write_text("# <Title>\n", encoding="utf-8")
        self.assertTrue(any("assets/note-template.md has no row" in error for error in self.broken(lambda t: t)))
        with_row = lambda t: t.replace("| --- | --- |\n", "| --- | --- |\n| [`note`](assets/note-template.md) | Template |\n")  # noqa: E731
        self.assertEqual(self.broken(with_row), [])
        (folder / "scripts").mkdir()
        (folder / "scripts/_shared.py").write_text('"""Shared code."""\n', encoding="utf-8")
        self.assertEqual(self.broken(with_row), [])
        (folder / "scripts/_shared.py").write_text("def broken(:\n", encoding="utf-8")
        self.assertTrue(any("does not parse" in error for error in self.broken(with_row)))
        (folder / "scripts/_shared.py").write_text("VALUE = 1\n", encoding="utf-8")
        self.assertTrue(any("module docstring" in error for error in self.broken(with_row)))
        (folder / "scripts/_shared.py").write_text('"""Shared code."""\n', encoding="utf-8")
        (folder / "notes").mkdir()
        self.assertTrue(any("notes/ is not a folder of the skill format" in error for error in self.broken(with_row)))

    def test_a_skills_directory_is_checked_skill_by_skill(self):
        self.write_skill("alpha")
        self.write_skill("beta", good_skill(self.root, "beta", "Does the work.").replace("name: beta", "name: gamma"))
        errors = self.errors("--path", ".skills", "--skip-registration")
        self.assertEqual(len(errors), 1, errors)
        self.assertTrue(all(error.startswith("beta: ") for error in errors))
        self.assertEqual(run("validate_skill.py", self.root, "--path", "missing")[0], 1)


if __name__ == "__main__":
    unittest.main()
