#!/usr/bin/env python3
"""Open a run of a skill, write the run's record, check the stored records and look earlier records up.

Records live in <skills directory>/.records/<skill>/<YYYY-MM-DD>.jsonl, one JSON object per line, append-only.
The record contract (when a run records, what each field means, the causes, the improvements) is owned by
../references/run-evaluation.md; this tool only enforces the structure of that contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import RECORDS, SEMVER, SKILLS_DIR, SLUG, SkillError, emit, read_skill, recorded_steps, resolve, shown  # noqa: E402

SCHEMA = "skill-record/v1"
FIELDS = ("run_ref", "request", "outcome", "steps", "decisions", "evaluation", "issues", "fixes", "supersedes")
RUN_REF = ("skill", "path", "version", "digest", "recorded_steps", "started_at")
OUTCOMES = ("completed", "blocked", "failed")
STEP_STATUSES = ("done", "skipped", "blocked", "failed", "not_reached")
MODES = ("agent", "self")
RESULTS = ("clean", "issues")
CAUSES = ("instruction", "ineffective_fix", "input", "execution")
FIX_STATUSES = ("applied", "pending_user")
PENDING_REASONS = ("safety", "repository")
DIGEST = re.compile(r"[0-9a-f]{12}")
DECISION_ID = re.compile(r"DEC-\d{2,}")
ISSUE_ID = re.compile(r"ISSUE-\d{2,}")
FIX_ID = re.compile(r"FIX-\d{2,}")
STEP_REF = re.compile(r"STEP-(\d{2,})")
PRIOR_FIX = re.compile(r"(.+)#(FIX-\d{2,})")


# ---------- the skill a run applies ----------


def digest(skill: Path) -> str:
    """A hash of every file of the skill folder, so a record names the exact rules its run applied."""

    total = hashlib.sha256()
    for path in sorted(item for item in skill.rglob("*") if item.is_file() and "__pycache__" not in item.parts):
        total.update(path.relative_to(skill).as_posix().encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
    return total.hexdigest()[:12]


def start(root: Path, skill_arg: str) -> dict[str, Any]:
    skill = resolve(skill_arg, root)
    meta, body = read_skill(skill)
    covered = recorded_steps(body, f"{skill.name}/SKILL.md")
    return {"run_ref": {
        "skill": str(meta.get("name", "")),
        "path": shown(skill, root),
        "version": str((meta.get("metadata") or {}).get("version", "")),
        "digest": digest(skill),
        "recorded_steps": covered,
        "started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }}


# ---------- reading ----------


def read_records(root: Path, skills_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Every stored record in file order, plus an error for each line that cannot be read."""

    records, errors = [], []
    for path in sorted((skills_dir / RECORDS).glob("*/*.jsonl")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            where = f"{shown(path, root)}:{number}"
            try:
                data = json.loads(line)
            except ValueError:
                errors.append(f"{where}: the line is not valid JSON")
                continue
            if not isinstance(data, dict):
                errors.append(f"{where}: a record must be a JSON object")
                continue
            records.append({**data, "_location": where})
    return records, errors


# ---------- validation ----------


def text(value: Any, label: str, errors: list[str]) -> str:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: non-empty text is required")
        return ""
    return value


def entries(value: Any, label: str, errors: list[str]) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        errors.append(f"{label}: expected an array of objects")
        return []
    return value


def choice(value: Any, allowed: tuple[str, ...], label: str, errors: list[str]) -> None:
    if value not in allowed:
        errors.append(f"{label}: expected one of {', '.join(allowed)}")


def unique_id(item: dict[str, Any], pattern: re.Pattern, seen: set[str], label: str, errors: list[str]) -> str:
    value = item.get("id")
    if not isinstance(value, str) or not pattern.fullmatch(value):
        errors.append(f"{label}.id: expected the form {pattern.pattern}")
        return ""
    if value in seen:
        errors.append(f"{label}.id: {value} is used twice")
    seen.add(value)
    return value


def check_run_ref(ref: Any, errors: list[str]) -> int:
    """Check the object `start` returned; return the number of steps the record covers."""

    if not isinstance(ref, dict) or set(ref) != set(RUN_REF):
        errors.append(f"run_ref: copy the object `start` returned, with exactly {', '.join(RUN_REF)}")
        return 0
    if not isinstance(ref["skill"], str) or not SLUG.fullmatch(ref["skill"]):
        errors.append("run_ref.skill: expected the name of the skill")
    text(ref["path"], "run_ref.path", errors)
    if not SEMVER.fullmatch(str(ref["version"])):
        errors.append("run_ref.version: expected <major>.<minor>.<patch>")
    if not DIGEST.fullmatch(str(ref["digest"])):
        errors.append("run_ref.digest: expected the 12 hexadecimal characters `start` returned")
    try:
        if datetime.fromisoformat(str(ref["started_at"])).tzinfo is None:
            raise ValueError
    except ValueError:
        errors.append("run_ref.started_at: expected the ISO-8601 timestamp with a UTC offset that `start` returned")
    if type(ref["recorded_steps"]) is not int or ref["recorded_steps"] < 1:
        errors.append("run_ref.recorded_steps: expected the number `start` returned")
        return 0
    return ref["recorded_steps"]


def check_record(data: dict[str, Any]) -> list[str]:
    """Structure errors of one record, without the fields the tool adds."""

    errors: list[str] = []
    missing, unknown = [key for key in FIELDS if key not in data], [key for key in data if key not in FIELDS]
    if missing or unknown:
        return [f"missing fields: {', '.join(missing) or 'none'}; unknown fields: {', '.join(unknown) or 'none'}"]
    total = check_run_ref(data["run_ref"], errors)
    text(data["request"], "request", errors)

    outcome = data["outcome"] if isinstance(data["outcome"], dict) else {}
    choice(outcome.get("status"), OUTCOMES, "outcome.status", errors)
    text(outcome.get("summary"), "outcome.summary", errors)

    steps = entries(data["steps"], "steps", errors)
    if total and [item.get("step") for item in steps] != list(range(1, total + 1)):
        errors.append(f"steps: one entry per step before the closing steps, in order, numbered 1 to {total}")
    for index, item in enumerate(steps, 1):
        choice(item.get("status"), STEP_STATUSES, f"steps[{index}].status", errors)
        text(item.get("note"), f"steps[{index}].note", errors)

    def step_in_range(value: Any) -> bool:
        return type(value) is int and 1 <= value <= (total or value)

    decisions: set[str] = set()
    for index, item in enumerate(entries(data["decisions"], "decisions", errors), 1):
        label = f"decisions[{index}]"
        unique_id(item, DECISION_ID, decisions, label, errors)
        if not step_in_range(item.get("step")):
            errors.append(f"{label}.step: expected the number of the step that made the decision")
        text(item.get("decision"), f"{label}.decision", errors)
        text(item.get("basis"), f"{label}.basis", errors)

    evaluation = data["evaluation"] if isinstance(data["evaluation"], dict) else {}
    choice(evaluation.get("mode"), MODES, "evaluation.mode", errors)
    choice(evaluation.get("result"), RESULTS, "evaluation.result", errors)

    issues: set[str] = set()
    for index, item in enumerate(entries(data["issues"], "issues", errors), 1):
        label = f"issues[{index}]"
        unique_id(item, ISSUE_ID, issues, label, errors)
        if not isinstance(item.get("issue_key"), str) or not SLUG.fullmatch(item["issue_key"]):
            errors.append(f"{label}.issue_key: expected a kebab-case key")
        subject, step = item.get("subject"), STEP_REF.fullmatch(str(item.get("subject")))
        if subject not in decisions and not (step and step_in_range(int(step.group(1)))):
            errors.append(f"{label}.subject: expected the id of a decision of this record, or STEP-NN for a step the record covers")
        choice(item.get("cause"), CAUSES, f"{label}.cause", errors)
        for key in ("problem", "rule", "evidence"):
            text(item.get(key), f"{label}.{key}", errors)
        prior = item.get("prior_fix")
        if item.get("cause") == "ineffective_fix":
            if not isinstance(prior, str) or not PRIOR_FIX.fullmatch(prior):
                errors.append(f"{label}.prior_fix: expected <record_id>#FIX-NN, the earlier fix that did not hold")
        elif prior is not None:
            errors.append(f"{label}.prior_fix: only an issue with the cause ineffective_fix names one")

    fixes: set[str] = set()
    fixed: set[str] = set()
    for index, item in enumerate(entries(data["fixes"], "fixes", errors), 1):
        label = f"fixes[{index}]"
        unique_id(item, FIX_ID, fixes, label, errors)
        named = item.get("issues")
        if not isinstance(named, list) or not named or any(issue not in issues for issue in named):
            errors.append(f"{label}.issues: expected the ids of the issues of this record that the fix addresses")
        else:
            fixed.update(named)
        choice(item.get("status"), FIX_STATUSES, f"{label}.status", errors)
        if item.get("status") == "pending_user":
            choice(item.get("reason"), PENDING_REASONS, f"{label}.reason", errors)
        elif item.get("reason") is not None:
            errors.append(f"{label}.reason: only a fix that is pending_user names one")
        files = entries(item.get("files"), f"{label}.files", errors)
        if not files:
            errors.append(f"{label}.files: name each file and section the fix edits")
        for number, file in enumerate(files, 1):
            text(file.get("path"), f"{label}.files[{number}].path", errors)
            text(file.get("section"), f"{label}.files[{number}].section", errors)
        text(item.get("summary"), f"{label}.summary", errors)
        checks = item.get("checks")
        if not isinstance(checks, list) or not all(isinstance(check, str) and check.strip() for check in checks):
            errors.append(f"{label}.checks: expected an array of the check commands that were run")
        elif item.get("status") == "applied" and not checks:
            errors.append(f"{label}.checks: an applied fix names the checks that were run after it")

    if issues - fixed:
        errors.append(f"every issue belongs to at least one fix; without one: {', '.join(sorted(issues - fixed))}")
    if (evaluation.get("result") == "issues") != bool(issues):
        errors.append("evaluation.result: `issues` exactly when the record has issues, otherwise `clean`")
    if data["supersedes"] is not None and not isinstance(data["supersedes"], str):
        errors.append("supersedes: expected the record_id of the record this one corrects, or null")
    return errors


def check_references(data: dict[str, Any], earlier: dict[str, dict[str, Any]]) -> list[str]:
    """A record may point only to records stored before it, and of the same skill."""

    errors = []
    skill = (data.get("run_ref") or {}).get("skill") if isinstance(data.get("run_ref"), dict) else None

    def same_skill(record_id: str) -> bool:
        return record_id in earlier and (earlier[record_id].get("run_ref") or {}).get("skill") == skill

    if isinstance(data.get("supersedes"), str) and not same_skill(data["supersedes"]):
        errors.append(f"supersedes: {data['supersedes']} is not an earlier record of this skill")
    for item in data.get("issues") if isinstance(data.get("issues"), list) else []:
        match = PRIOR_FIX.fullmatch(str(item.get("prior_fix"))) if isinstance(item, dict) and item.get("prior_fix") else None
        if match and not (same_skill(match.group(1))
                          and any(fix.get("id") == match.group(2) for fix in earlier[match.group(1)].get("fixes", []))):
            errors.append(f"prior_fix: {item['prior_fix']} is not a fix of an earlier record of this skill")
    return errors


def check_stored(root: Path, skills_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    records, errors = read_records(root, skills_dir)
    earlier: dict[str, dict[str, Any]] = {}
    for record in records:
        where = record["_location"]
        body = {key: value for key, value in record.items() if key not in ("schema", "record_id", "recorded_at", "_location")}
        found = check_record(body) + check_references(body, earlier)
        if record.get("schema") != SCHEMA:
            found.append(f"schema: expected {SCHEMA}")
        record_id = record.get("record_id")
        if not isinstance(record_id, str) or not record_id or record_id in earlier:
            found.append("record_id: missing, or already used by an earlier record")
        else:
            earlier[record_id] = record
        errors += [f"{where}: {error}" for error in found]
    return records, errors


# ---------- commands ----------


def append(root: Path, data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SkillError("the input must be one JSON object")
    errors = check_record(data)
    if errors:
        return {"passed": False, "errors": errors}
    ref = data["run_ref"]
    skill = resolve(ref["path"], root)
    meta, _ = read_skill(skill)
    if meta.get("name") != ref["skill"]:
        raise SkillError(f"run_ref.path names the skill `{meta.get('name')}`, not `{ref['skill']}`")
    skills_dir = skill.parent
    stored, _ = check_stored(root, skills_dir)
    errors = check_references(data, {record["record_id"]: record for record in stored if isinstance(record.get("record_id"), str)})
    if errors:
        return {"passed": False, "errors": errors}

    now = datetime.now().astimezone()
    line = json.dumps(data, ensure_ascii=False, sort_keys=True)
    record_id = f"{now:%Y%m%d-%H%M%S}-{hashlib.sha256((line + now.isoformat()).encode('utf-8')).hexdigest()[:6]}"
    record = {"schema": SCHEMA, "record_id": record_id, "recorded_at": now.isoformat(timespec="seconds"), **data}
    folder = skills_dir / RECORDS
    target = folder / ref["skill"] / f"{now:%Y-%m-%d}.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    ignore = folder / ".gitignore"
    if not ignore.exists():
        # Records describe the user's projects, so they stay out of Git until the user decides otherwise; an existing file is never changed.
        ignore.write_text("*\n", encoding="utf-8", newline="\n")
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    result = {"passed": True, "record_id": record_id, "path": shown(target, root)}
    stored_errors = check_stored(root, skills_dir)[1]
    if stored_errors:
        result.update({"passed": False, "errors": stored_errors})
    return result


def check(root: Path, skills_dir: Path) -> dict[str, Any]:
    records, errors = check_stored(root, skills_dir)
    return {"passed": not errors, "records": len(records), **({"errors": errors} if errors else {})}


def query(root: Path, skills_dir: Path, skill: str | None, issue_keys: list[str], rules: list[str], last: int | None,
          everything: bool) -> dict[str, Any]:
    """Earlier records, oldest first: of one skill, or holding an issue with one of the keys or one of the rules."""

    records, _ = read_records(root, skills_dir)
    superseded = {record.get("supersedes") for record in records}
    found = []
    for record in records:
        issues = [issue for issue in record.get("issues", []) if isinstance(issue, dict)]
        if skill and (record.get("run_ref") or {}).get("skill") != skill:
            continue
        if (issue_keys or rules) and not any(issue.get("issue_key") in issue_keys or issue.get("rule") in rules for issue in issues):
            continue
        if record.get("record_id") in superseded and not everything:
            continue
        found.append({key: value for key, value in record.items() if key != "_location"})
    return {"passed": True, "records": found[-last:] if last else found}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--root", type=Path, default=Path.cwd(), help="root of the repository (default: the current directory)")
    commands = parser.add_subparsers(dest="command", required=True)
    opening = commands.add_parser("start", parents=[shared], help="pin the version of the skill a run applies; writes nothing")
    opening.add_argument("--skill", required=True, help="path of the skill folder, relative to the root or absolute")
    writing = commands.add_parser("append", parents=[shared], help="check one record and store it")
    writing.add_argument("--input", help="UTF-8 file holding the record as JSON; default: standard input")
    for name, text_ in (("check", "check every stored record"), ("query", "list earlier records")):
        command = commands.add_parser(name, parents=[shared], help=text_)
        command.add_argument("--skills-dir", default=SKILLS_DIR, help=f"directory that holds the skills; default: {SKILLS_DIR}")
        if name == "query":
            command.add_argument("--skill", help="only the records of the skill with this name")
            command.add_argument("--issue-key", action="append", default=[], help="records holding an issue with this key; repeatable")
            command.add_argument("--rule", action="append", default=[], help="records holding an issue about this rule, as file#section; repeatable")
            command.add_argument("--last", type=int, help="only the most recent N matching records")
            command.add_argument("--all", action="store_true", help="include the records that a later record supersedes")
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        if args.command == "start":
            result = {"passed": True, **start(root, args.skill)}
        elif args.command == "append":
            raw = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
            result = append(root, json.loads(raw))
        elif args.command == "check":
            result = check(root, resolve(args.skills_dir, root))
        else:
            result = query(root, resolve(args.skills_dir, root), args.skill, args.issue_key, args.rule, args.last, args.all)
    except (SkillError, OSError, ValueError) as exc:
        result = {"passed": False, "errors": [str(exc)]}
    return emit(result)


if __name__ == "__main__":
    raise SystemExit(main())
