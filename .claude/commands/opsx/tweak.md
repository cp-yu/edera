---
name: "OPSX: Tweak"
description: "Create a lightweight change-lite (proposal + specs only, no design/tasks)"
category: Workflow
tags: [workflow, lightweight, transitional]
---

Create a lightweight change with proposal + specs delta only (no design/tasks).

I'll create a change-lite with:
- proposal.md (what & why, 1-3 sentences)
- specs delta (ADDED/MODIFIED/REMOVED requirements)
- opsx-delta.yaml (optional, only if architecture changes)

This workflow supports two paths:
- **Doc-first**: Generate specs first, then write code
- **Code-first**: Code already written, capture specs after

When ready, run /opsx:archive

---

**Input**: The argument after `/opsx:tweak` is the change name (kebab-case).

**Steps**

1. **If no input provided, ask for the change name**

   Use the **AskUserQuestion tool** (open-ended, no preset options) to ask:
   > "What is the change name? (kebab-case, e.g., fix-validation-bug)"

   Wait for response, then continue with the provided name.

2. **Create the tweak change**

   Run: `openspec new change "<name>" --schema tweak`

3. **Check status and understand schema**

   Run: `openspec status --change "<name>" --json`

   Parse the JSON to understand:
   - `schemaName`: Should be "tweak"
   - `artifacts`: Should contain proposal, specs, opsx-delta (optional)

4. **Load shared OPSX context**

   Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
- Treat it as navigation context, not as a replacement for change artifacts

5. **Check for existing specs coverage**

   Run: `openspec list --specs --json`

   Build the cap→spec mapping from each spec's `capabilities` string array. Specs without frontmatter return `capabilities: []`.

6. **Use CLI-backed OPSX navigation**

   After reading shared `project.opsx.yaml` context, use OpenSpec CLI query surfaces for node details.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays; specs without frontmatter return `capabilities: []`.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id...> --json` to get node details, relations and code-map refs in one batch; add `--depth 2` when broader related context is needed.
- Treat CLI output as navigation context, not as a replacement for change artifacts.

7. **Generate proposal.md**

   Run: `openspec instructions proposal --change "<name>" --json`

   Read `configProjection`, `template`, `instruction`, and `outputPath`.

   Create proposal.md following the template. Keep it concise (1-3 sentences for Why).

8. **Generate specs delta**

   Run: `openspec instructions specs --change "<name>" --json`

   Read `configProjection`, `template`, `instruction`, and `outputPath`.

   Create one spec file per capability in specs/<capability>/spec.md. Use ADDED/MODIFIED/REMOVED sections.

9. **Optionally generate opsx-delta.yaml**

   If architecture changes occurred (new/modified/removed capabilities, domains, or relations):

   Run: `openspec instructions opsx-delta --change "<name>" --json`

   Create opsx-delta.yaml with `schema_version: 1`, `ADDED:`, `MODIFIED:`, and `REMOVED:` YAML keys.

10. **Run post-propose validation (warning-only)**

    Run: `openspec validate "<name>" --type change --json`

    If warnings appear, do one repair pass and re-check.

11. **Show status and usage paths**

    Run: `openspec status --change "<name>"`

    Explain:
    - **Doc-first**: Use generated specs to guide code implementation
    - **Code-first**: Code already written, specs capture what changed
    - When ready: `/opsx:archive "<name>"`

**Note**: tweak is a transitional workflow for current LLM limitations. When LLM improves, use propose→apply instead.
