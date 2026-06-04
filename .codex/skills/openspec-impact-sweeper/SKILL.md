---
name: openspec-impact-sweeper
description: Generate a lightweight OPSX-grounded JSON impact report for one project concept. Use from explore before scope or proposal readiness claims.
license: MIT
compatibility: Requires openspec CLI project files.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0-cpyu.9"
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

## Evidence Protocol

1. Query OPSX first through the CLI. For each plausible node ID, run:
   ```bash
   openspec opsx query <node-id> --json
   ```
   Use the returned `node`, `relations`, and `codeMap` fields as evidence. If the command reports "OPSX files not found", record that phrase in coverageGaps, add a bootstrap question, and continue with repository search.
2. Map the user term and concept to plausible project terms. Include all plausible mappings in termMappings.
3. For matched OPSX nodes, read node intent, code-map refs, and one-hop relations.
4. Expand to second-hop relations only when the first-hop node is shared infrastructure, crosses domains, or code search shows outward runtime use.
5. When optionalChangeName is provided, read only that change's proposal.md, design.md, tasks.md, specs/**/*.md, and opsx-delta.yaml if present. Do not inspect unrelated active changes.
6. Use git ls-files as the repository search boundary when available. Exclude openspec/changes/archive/**.
7. Perform repo-wide reverse search across tracked files for mapped project terms, exported symbols, workflow names, skill names, command names, configuration keys, template fragment names, and path references.
8. Build the cap→spec mapping through:
   ```bash
   openspec list --specs --json
   ```
   Extract each spec entry's `capabilities` string array. Treat a missing frontmatter mapping as an empty array. Add specs linked to affected caps to mustCheck with the CLI output as evidence.
9. When reading mustCheck specs and the caller provided `concept`, perform the Terminology Awareness step below.
10. Do not rely only on OPSX code-map paths. Classify findings into mustChange, mustCheck, coverageGaps, and questions.

## Terminology Awareness

Identify terms semantically related to user's `concept` input while reading mustCheck specs. Extract only domain terms close to that concept, not every noun in the file; if concept is '流程', extract '工作流', 'workflow', '工作流程' etc. and ignore unrelated terms such as '拓扑排序' or '制品'.

For each extracted term, count occurrences and record the spec names where it appears. Use the spec identifier returned by `openspec list --specs --json` when available; otherwise use the spec directory name without path prefixes or file extensions. Sort extracted terms by descending count, then by term.

Record in `terminologyObservations` field:

```json
{
  "userInput": "string",
  "foundInSpecs": [
    {
      "term": "string",
      "specs": ["string"],
      "count": 1
    }
  ]
}
```

Report facts only, no judgment or recommendations. Do not decide whether terms are correct or should be unified. If terminology extraction fails, omit `terminologyObservations` and keep the report usable with normal impact fields.

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

## JSON Report Schema

```json
{
  "concept": "string",
  "projectRoot": "string",
  "terminologyObservations": {
    "userInput": "string",
    "foundInSpecs": [
      {
        "term": "string",
        "specs": ["string"],
        "count": 1
      }
    ]
  },
  "termMappings": [
    {
      "userTerm": "string",
      "projectTerms": ["string"],
      "evidence": ["string"]
    }
  ],
  "opsx": {
    "nodes": [
      {
        "id": "string",
        "reason": "string"
      }
    ],
    "relationsExpanded": [
      {
        "from": "string",
        "to": "string",
        "type": "string"
      }
    ],
    "coverageGaps": ["string"]
  },
  "mustChange": [
    {
      "target": "string",
      "reason": "string",
      "evidence": ["string"]
    }
  ],
  "mustCheck": [
    {
      "target": "string",
      "reason": "string",
      "evidence": ["string"]
    }
  ],
  "coverageGaps": ["string"],
  "questions": ["string"]
}
```

Field names are canonical. Item values may use natural language. Reports under openspec/sweeper/ are working notes, not proposal, design, tasks, specs, OPSX delta, sync input, or archive input.

## Output Contract

On success, return only the report path, for example:

```
openspec/sweeper/impact-sweep-explore-impact-sweep.json
```

Do not emit a separate summary.
