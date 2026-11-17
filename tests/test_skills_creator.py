"""Check the skills-creator skill as a package and run its scripts against temporary repositories."""
from __future__ import annotations

import json
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

## Procedure

1. **Open the task.** Read the inputs.
2. **Report.** Say what changed.
"""


def run(script: str, root: Path, *args: str) -> tuple[int, dict]:
    result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(SCRIPTS / script), "--root", str(root), *args],
                            capture_output=True, text=True, encoding="utf-8")
    return result.returncode, json.loads(result.stdout)


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
        (folder / "SKILL.md").write_text(text or GOOD_SKILL.format(name=name, description=description), encoding="utf-8")
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

    def test_scripts_run_on_the_oldest_supported_syntax(self):
        # Every script opts into postponed annotations, which keeps `X | None` hints valid on Python 3.9.
        for script in sorted(SCRIPTS.glob("*.py")) + [SKILL / "assets" / "script-template.py"]:
            with self.subTest(script=script.name):
                self.assertIn("from __future__ import annotations", script.read_text(encoding="utf-8"))


class NewSkillTests(Repository):
    def test_thin_skill_is_scaffolded_filled_and_validated(self):
        code, result = run("new_skill.py", self.root, "--name", "release-notes", "--size", "thin")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["files"], [".skills/release-notes/SKILL.md"])
        self.assertTrue(any("placeholder" in error for error in self.errors("--path", result["path"], "--skip-registration")))
        fill(self.root / result["path"])
        self.assertEqual(self.errors("--path", result["path"], "--skip-registration"), [])

    def test_full_skill_is_scaffolded_and_its_script_creates_the_artifact(self):
        code, result = run("new_skill.py", self.root, "--name", "incident-report", "--size", "full", "--artifact", "post-mortem")
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
                code, result = run("new_skill.py", self.root, *args)
                self.assertEqual((code, result["passed"]), (1, False))
                self.assertFalse((self.root / ".skills").exists())
        self.assertEqual(run("new_skill.py", self.root, "--name", "report", "--size", "thin")[0], 0)
        before = (self.root / ".skills/report/SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(run("new_skill.py", self.root, "--name", "report", "--size", "full", "--artifact", "note")[0], 1)
        self.assertEqual((self.root / ".skills/report/SKILL.md").read_text(encoding="utf-8"), before)
        self.assertFalse((self.root / ".skills/report/assets").exists())

    def test_skills_directory_can_be_named(self):
        code, result = run("new_skill.py", self.root, "--name", "report", "--size", "thin", "--skills-dir", "tools/skills")
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
        self.assertEqual(self.register("--file", "CLAUDE.md"), {"CLAUDE.md": "created"})
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(self.errors("--path", ".skills/alpha"), [])

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


class ValidatorTests(Repository):
    def broken(self, change, name: str = "work") -> list[str]:
        """The validator's errors for a good skill after one change to its SKILL.md."""

        folder = self.root / ".skills" / name
        if not folder.exists():
            self.write_skill(name)
        entry = folder / "SKILL.md"
        entry.write_text(change(GOOD_SKILL.format(name=name, description="Does the work.")), encoding="utf-8")
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
        self.assertTrue(any("level-two sections" in error for error in self.broken(lambda t: t)))
        with_section = lambda t: t.replace("## Procedure", "## Resources\n\n| Resource | Use |\n| --- | --- |\n\n## Procedure")  # noqa: E731
        self.assertTrue(any("assets/note-template.md has no row" in error for error in self.broken(with_section)))
        with_row = lambda t: with_section(t).replace("| --- | --- |\n", "| --- | --- |\n| [`note`](assets/note-template.md) | Template |\n")  # noqa: E731
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
        self.write_skill("beta", GOOD_SKILL.format(name="gamma", description="Does the work."))
        errors = self.errors("--path", ".skills", "--skip-registration")
        self.assertEqual(len(errors), 2, errors)
        self.assertTrue(all(error.startswith("beta: ") for error in errors))
        self.assertEqual(run("validate_skill.py", self.root, "--path", "missing")[0], 1)


if __name__ == "__main__":
    unittest.main()
