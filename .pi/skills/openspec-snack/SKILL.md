---
name: "openspec-snack"
description: "Quick code-first sync: generate or update proposal + specs + simplified design from git diff when the code is already written. Use after iterative coding to back-fill specs and OPSX delta without redoing propose→apply. Does not generate tasks.md."
license: "MIT"
compatibility: "Requires openspec CLI."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

Synchronize specs and OPSX from already-written code (code-first, reverse of propose/apply).

## Input

- Optional `<change-name>` (kebab-case).
- If omitted, run `openspec list --json` and reuse the single active change; if multiple or none, ask which change name to target.

## Flow

1. Resolve change name. If `openspec/changes/<name>/` does not exist, run `openspec new change "<name>"`; otherwise update in place (do not recreate proposal).
2. Load shared OPSX context before generating artifacts.
Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
- Treat it as navigation context, not as a replacement for change artifacts
3. Analyze the code change with git diff.
   - Run `git diff --name-only` (and `git diff --cached --name-only` when needed) to list modified files.
   - Run `git diff` to inspect symbol-level changes (new/deleted exports, modified signatures).
   - Exclude non-code files (`.md`, `.json`, `.yaml`, lock files) from spec inference.
4. Reverse-map files to capabilities via code-map.
   - Read `openspec/project.opsx.code-map.yaml` and map each modified path to its capability/domain node IDs.
   - Files without a code-map entry are [REVIEW NEEDED] candidates for new capabilities.
5. Use CLI-backed OPSX navigation after code-map reverse lookup.
After reading shared `project.opsx.yaml` context, use OpenSpec CLI query surfaces for node details.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays; specs without frontmatter return `capabilities: []`.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id...> --json` to get node details, relations and code-map refs in one batch; add `--depth 2` when broader related context is needed.
- Treat CLI output as navigation context, not as a replacement for change artifacts.
6. Determine the capability list first, then generate `proposal.md`.
   - Run `openspec instructions proposal --change "<name>" --json`.
   - Use the returned `template`, `instruction`, `outputPath`, and `configProjection`; do not invent non-template sections.
   - Determine the `## Capabilities` list before specs generation and reuse the same list as specs input.
   - Prefer code-map reverse lookup; files without code-map coverage may use git diff inference but MUST be marked `[REVIEW NEEDED]`.
   - Preserve the template headings including `## Why`, `## What Changes`, `## Capabilities`, and `## Impact`.
7. Generate delta specs in `specs/<capability>/spec.md` from the artifact instruction.
   - Run `openspec instructions specs --change "<name>" --json`.
   - Use the returned `template`, `instruction`, `outputPath`, and `configProjection`; do not invent non-template sections.
   - Follow the returned `instruction` for ADDED/MODIFIED selection, spec directory naming, and MODIFIED requirement title matching.
   - Reuse an existing `openspec/specs/<capability>/` directory when the instruction says it applies; otherwise use the proposal capability name.
   - New concerns use `## ADDED Requirements`; changed existing behavior uses `## MODIFIED Requirements` with the exact existing Requirement title.
   - Requirement text MUST contain SHALL/MUST language and at least one `#### Scenario:` block with WHEN/THEN style.
   - Mark uncertain inferences with `[REVIEW NEEDED]`.
8. Generate simplified `design.md` from the artifact instruction.
   - Run `openspec instructions design --change "<name>" --json`.
   - Use the returned `template`, `instruction`, `outputPath`, and `configProjection`; do not invent non-template sections.
   - Preserve the full template skeleton: Context, Goals / Non-Goals, Decisions, and Risks / Trade-offs.
   - Mark inferred content with `[INFERRED FROM CODE]`; mark unresolved risks or trade-offs with `[REVIEW NEEDED]`.
9. OPSX delta heuristic — generate `opsx-delta.yaml` ONLY when git diff shows new/deleted exports or new files; otherwise skip and log "No architecture-level changes detected. Skipping OPSX delta generation".
   **Generate opsx-delta.yaml**:
- Read `openspec instructions opsx-delta --change "<name>" --json`
- Use the returned `template`, `instruction`, and `outputPath` to generate `opsx-delta.yaml`
- Read `proposal.md` to extract the capability list
- Read all delta specs in `openspec/changes/<name>/specs/*/spec.md`
- For existing capability or domain IDs, run `openspec opsx query <node-id...> --json` for current-system context in one batch; add `--depth 2` when related context is needed
- Treat `ADDED`, `MODIFIED`, and `REMOVED` as YAML object keys, not Markdown headings
- Follow a concrete YAML object structure such as:
  ```yaml
  schema_version: 1
  ADDED:
    capabilities:
      - id: cap.example.feature
        type: capability
        intent: Describe the new capability
    relations:
      - from: cap.example.feature
        type: contains
        to: dom.example
  MODIFIED:
    capabilities:
      - id: cap.example.existing
        intent: Updated intent text
  REMOVED:
    capabilities:
      - id: cap.example.legacy
  ```
- Delta nodes contain only id, type, intent, status — no code_refs or spec_refs
- Keep this agent-driven: capture merge intent in the YAML, not in programmatic code
10. Do NOT generate `tasks.md` (code is already implemented).
11. Run `openspec validate "<name>" --type change --json` after all generated artifacts are written.
   - If validation returns ERROR or WARNING, run one repair pass using the relevant artifact `instruction` rules, then run `openspec validate "<name>" --type change --json` once more.
   - Treat the second validation result as final evidence.
   - Output validate result: if passed, indicate self-check passed; if ERROR/WARNING remain, list each and advise user review.
12. Finish with the output hints below, including the validate result.

## Output Hints

After artifacts are generated, output:

**Fast path (skip verify):**
  • Continue development: `openspec sync "<change-name>" --no-verify`
  • Fast archive: `openspec archive "<change-name>" --no-verify`

**Correction path:**
⚠️ Generated specs are based on code inference. Review items marked [REVIEW NEEDED]
- Correction branch 1: review change → manually edit specs → sync → archive
- Correction branch 2: review change → modify code → run `/opsx-snack` again → continue iterating

## Artifact Contract

**Document Language Contract**:
- Treat `openspec/config.yaml` as the compact source of truth, but consume its compiled prompt projection rather than reinterpreting raw keys ad hoc
- If the compiled projection includes `proseLanguage`, apply it to natural-language prose you write or revise in the artifact body
- Natural-language prose includes task titles, check names, Requirement titles, Scenario titles, bullet descriptions, Expect/Evidence descriptions, rationale, goals, risks, and summaries
- Follow the existing template structure exactly; do not invent a different layout because the prose language changes
- Keep template headings, normative keywords, BDD keywords, IDs, schema keys, relation types, file paths, commands, and code identifiers in their canonical form
- Preserve exact existing Requirement titles required for MODIFIED matching
- English project terminology may remain embedded in prose, but ordinary English sentences and titles still follow `proseLanguage`
- If no `proseLanguage` projection is present, keep the default writing behavior for prose

Keep generated specs coarse and behavior-focused; preserve template headings, canonical IDs, schema keys, BDD keywords, paths, commands, and code identifiers.
