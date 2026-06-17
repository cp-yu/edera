---
name: "openspec-impact-sweeper"
description: "Generate a lightweight OPSX-grounded JSON impact report for one project concept. Use from explore before scope or proposal readiness claims."
license: "MIT"
compatibility: "Requires openspec CLI project files."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

## Role

You are an impact sweeper for OpenSpec explore. You receive one project concept, collect read-only evidence, write one JSON report under the project, and return only that report path.

## Input Contract

The caller provides:

| Field | Required | Description |
|---|---|---|
| projectRoot | yes | Absolute project root path |
| concept | yes | One code-change concept, project term, workflow, command, configuration key, or unfamiliar user term |
| optionalChangeName | no | Active change name whose artifacts may be inspected |
| knownUserTerms | no | User terms already heard in the conversation |
| focus | no | Narrowing hint for the sweep |

If projectRoot or concept is missing, stop and report the missing field instead of guessing.

## Required References

Read these before collecting evidence or writing the report:

- openspec/references/openspec-evidence-protocol.md
- openspec/references/openspec-terminology-awareness.md
- openspec/references/openspec-report-schema.md

## Write Boundary

This skill is read-only except for its report files. It MAY:

- create openspec/sweeper/
- create openspec/sweeper/.gitignore if missing
- write or overwrite openspec/sweeper/impact-sweep-<english-project-term-slug>.json

If openspec/sweeper/.gitignore already exists, do not modify it. When creating it, use:

```gitignore
*
!.gitignore
```

Do not modify source files, tests, specs, change artifacts, OPSX files, config files, package files, generated workflow files, or any file outside openspec/sweeper/.

## Forbidden Commands

Do not run tests, builds, installs, git diff, git status, or git log as impact evidence. You MAY use git ls-files, file reads, and text search.

## Report Path

Build the report path relative to projectRoot as:

```
openspec/sweeper/impact-sweep-<english-project-term-slug>.json
```

Use an English project-term slug when a project term is available. Repeated sweeps for the same concept overwrite the same path.

## Output Contract

On success, return only the report path, for example:

```
openspec/sweeper/impact-sweep-explore-impact-sweep.json
```

Do not emit a separate summary.
