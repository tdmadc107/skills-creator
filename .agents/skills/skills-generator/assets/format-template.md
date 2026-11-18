# <Artifact name> format

The `{{name}}` skill owns how <an artifact> is laid out, named and stored.
<If another document owns what the content must settle: that document and what it owns>.

## Location and naming

- Output directory: the directory the user names; when the user names none, <the default directory>.
- File: `<slug>-<YYYYMMDD-HHmmss>.md`.
- Slugs are ASCII kebab-case: lowercase letters, digits and single hyphens.
- Timestamps use the machine's local time zone and carry its UTC offset.
- Creating <an artifact> never overwrites an existing file (the helper script refuses).

## Frontmatter

| Field | Value |
| --- | --- |
| `schema` | `{{name}}/v1` |
| `title` | <What the title names>, quoted |
| `created_at` | ISO-8601 timestamp with a UTC offset, quoted |
| `<field>` | <Its value, or its allowed values> |

## Body

- <The level-two sections, in their order, and what each one holds>.
- <The form of the lines that later work reads one by one>.

## Placeholders in the template

- `{{...}}`: computed values that `scripts/new_{{artifact_snake}}.py` fills in.
  When a file is written without the script, fill them by the rules above.
- `<...>`: content the agent writes from the decisions of the run.
  A line of the form `<If ...: ...>` stays only when its condition holds.
