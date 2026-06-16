---
name: openspec-tweak
description: Create a lightweight change-lite (proposal + specs delta only, no design/tasks). Use for quick spec-only changes or when code is already written. Supports doc-first (spec → code) or code-first (code → spec) workflows.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0-cpyu.9"
---

Create a lightweight change with proposal + specs delta only.

## Flow

1. Input must identify a kebab-case change name. If unclear, ask for the change name.
2. Run `openspec new change "<name>" --schema tweak`, then `openspec status --change "<name>" --json` to confirm schema and artifact list.
3. Load shared OPSX context before artifact generation.
Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
- Treat it as navigation context, not as a replacement for change artifacts
4. Before specs, run `openspec list --specs --json`; compare proposed capabilities to each spec's `capabilities` string array. Specs without frontmatter return `capabilities: []`. Reuse or modify existing coverage instead of duplicating specs.
5. Use CLI-backed OPSX navigation after shared context.
After reading shared `project.opsx.yaml` context, use OpenSpec CLI query surfaces for node details.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays; specs without frontmatter return `capabilities: []`.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id...> --json` to get node details, relations and code-map refs in one batch; add `--depth 2` when broader related context is needed.
- Treat CLI output as navigation context, not as a replacement for change artifacts.
6. For each artifact (proposal, specs), run `openspec instructions <artifact-id> --change "<name>" --json`; read `configProjection` (especially `configProjection.normalized.proseLanguage` and `configProjection.prompt.fragments`), dependencies, `template`, `instruction`, and `outputPath`; follow the template exactly and do not copy `context`, `rules`, or `configProjection` into artifact files. When creating `specs`, apply the returned `Spec content boundary`: route non-behavior content to design/tasks/proposal/opsx-delta instead of requirements.
7. After specs are complete, optionally generate `opsx-delta.yaml` if architecture changes occurred (new/modified/removed capabilities, domains, or relations). Use `openspec instructions opsx-delta --change "<name>" --json`; use `schema_version: 1`, `ADDED:`, `MODIFIED:`, and `REMOVED:` YAML keys and query existing nodes when needed.
8. Run warning-only post-propose validation: This validation is warning-only. Prefer `openspec validate "<name>" --type change --json`; align with `Validator.validateChangeDeltaSpecs()`, SHALL/MUST requirement text, required `#### Scenario:` blocks, `Validator.validateOpsxDelta()`, `applyOpsxDelta()`, referential integrity, and code-map integrity. Do NOT run `openspec sync`; report when validation skips this check. Do NOT validate tasks.md structure (tweak schema has no tasks). If warnings appear, do exactly one repair pass, re-check once, and summarize remaining warnings.
9. Finish with `openspec status --change "<name>"` and explain the two usage paths:
   - **Doc-first**: Use generated specs to guide code implementation, then run `$openspec-archive-change`
   - **Code-first**: Code is already written, specs capture what changed, then run `$openspec-archive-change`

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

Preserve template structure, canonical headings, IDs, schema keys, paths, commands, BDD keywords, and code identifiers.

## Transitional Tier Notice

tweak is a transitional workflow addressing current LLM limitations:
1. Unreliable spec→code generation quality
2. Long propose generation time (minutes) for small changes

When LLM capabilities improve (reliable spec→code + fast generation), tweak should be deprecated and all changes should use propose→apply.
