---
name: "openspec-propose"
description: "Propose a new change with all artifacts generated in one step. Use when the user wants to quickly describe what they want to build and get a complete proposal with design, specs, and tasks ready for implementation."
license: "MIT"
compatibility: "Requires openspec CLI."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

Propose a new change and generate all artifacts needed for implementation.

## Flow

1. Input must identify a kebab-case change name or enough description to derive one. If unclear, ask what to build or fix.
2. Apply smart routing before creating files: inspect the current conversation for an explore-generated `Design Summary`; if no summary exists, respect `propose.smartRouting: false` and `propose.requireExplore: false`, otherwise score the user's input across 5 dimensions. Detect multi-subsystem scope. Outcomes include: "Design Summary found: proceed and show that Design Summary is being used", "Input is sufficiently detailed. Skipping explore; generating artifacts directly.", and "This request spans multiple independent subsystems. Consider running `/opsx-explore` to decompose it first.". Show input length, detail score, multi-subsystem result, and final decision.
3. Run `openspec new change "<name>"`, then `openspec status --change "<name>" --json` to read `applyRequires`, artifact order, dependencies, and schema.
4. Load shared OPSX context before artifact generation.
Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
- Treat it as navigation context, not as a replacement for change artifacts
5. Before specs, run `openspec list --specs --json`; compare proposed capabilities to each spec's `capabilities` string array. Specs without frontmatter return `capabilities: []`. Reuse or modify existing coverage instead of duplicating specs.
6. Use CLI-backed OPSX navigation after shared context.
After reading shared `project.opsx.yaml` context, use OpenSpec CLI query surfaces for node details.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays; specs without frontmatter return `capabilities: []`.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id...> --json` to get node details, relations and code-map refs in one batch; add `--depth 2` when broader related context is needed.
- Treat CLI output as navigation context, not as a replacement for change artifacts.
7. For each ready artifact, run `openspec instructions <artifact-id> --change "<name>" --json`; read `configProjection` (especially `configProjection.normalized.proseLanguage` and `configProjection.prompt.fragments`), dependencies, `template`, `instruction`, and `outputPath`; follow the template exactly and do not copy `context`, `rules`, or `configProjection` into artifact files. When creating `specs`, apply the returned `Spec content boundary`: route non-behavior content to design/tasks/proposal/opsx-delta instead of requirements.
8. Continue until all `applyRequires` artifacts are `done`. If an artifact is unclear, ask one focused question and continue.
9. After spec-driven specs are complete, generate `opsx-delta.yaml` from `openspec instructions opsx-delta --change "<name>" --json`; use `schema_version: 1`, `ADDED:`, `MODIFIED:`, and `REMOVED:` YAML keys and query existing nodes when needed.
10. Run warning-only post-propose validation: This validation is warning-only. Do NOT turn `/opsx-propose` into a blocking gate. Prefer `openspec validate "<name>" --type change --json`; align with `Validator.validateChangeDeltaSpecs()`, SHALL/MUST requirement text, required `#### Scenario:` blocks, `Validator.validateOpsxDelta()`, `applyOpsxDelta()`, referential integrity, and code-map integrity. Do NOT run `openspec sync`; report when validation skips this check. For structure checks, read `openspec instructions proposal --change "<name>" --json`, `openspec instructions design --change "<name>" --json`, and `openspec instructions tasks --change "<name>" --json`; use `validateTaskStructure`, support Actions and coarse `### Task N:` with Goal, Files, Requirements, Checks, Covers:, Verifies:, change-local `Verifies:` spec paths, Requirement/Scenario references, Command:, Evidence:, and Expect:. Do NOT invent semantic lint rules beyond the current templates. Do NOT judge whether a check is semantically sufficient. If warnings appear, do exactly one repair pass, re-check once, and summarize remaining warnings.
11. Finish with `openspec status --change "<name>"` and report artifacts created plus readiness for `/opsx-apply`.

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

Keep generated tasks coarse: `### Task N:`, `Goal`, `Files`, `Requirements`, and nested Checks. Keep each task to at most 5 Requirements. Preserve template structure, canonical headings, IDs, schema keys, paths, commands, BDD keywords, and code identifiers.
