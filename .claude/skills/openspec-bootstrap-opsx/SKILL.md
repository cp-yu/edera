---
name: openspec-bootstrap-opsx
description: Bootstrap OPSX architecture map from existing codebase using a structured five-phase workflow (init → scan → map → review → promote).
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "2.0"
  generatedBy: "1.2.0-cpyu.4"
---

Bootstrap the OPSX architecture map from the existing codebase.

This is a **structured, multi-phase** workflow. Each phase produces intermediate artifacts in `openspec/bootstrap/` before writing formal OPSX files.

**Input**: No argument required. Scope hints (folders, domain names) are passed to init.

**Steps**

1. **Determine current phase**
   ```bash
   openspec bootstrap status --json
   ```
   - If no workspace exists, start with init
   - If workspace exists, resume from the current phase

2. **Execute the current phase**

   Get phase-specific instructions:
   ```bash
   openspec bootstrap instructions [phase] --json
   ```

   **Phase: init**
   ```bash
   openspec bootstrap init --mode full
   ```
   Creates workspace at `openspec/bootstrap/` with scope configuration.
   Supported upgrade paths:
   - `specs-based -> full`
   - `raw -> full`
   - `raw -> opsx-first`
   Use `opsx-first` only for `raw` repositories when you want the formal OPSX bundle plus a README-only specs starter now, and full behavior specs later.

   **Phase: scan**
   - Read `package.json`, `README`, OpenSpec config, `openspec/specs/`
   - Scan source code for structural boundaries
   - Write `openspec/bootstrap/evidence.yaml` with candidate domains:
     ```yaml
     domains:
       - id: dom.cli
         confidence: high
         sources: [code:src/cli/, spec:openspec/specs/cli/]
         intent: CLI entry point and command routing
     ```
   - Run `openspec bootstrap validate` to verify gates

   **Phase: map**
   - For each domain in evidence.yaml, create `openspec/bootstrap/domain-map/<domain-id>.yaml`:
     ```yaml
     domain:
       id: dom.cli
       type: domain
       intent: CLI entry point and command routing
       status: active
     capabilities:
       - id: cap.cli.init
         type: capability
         intent: Initialize OpenSpec in a project
         status: active
     relations:
       - from: cap.cli.init
         to: dom.cli
         type: contains
     code_refs:
       - id: cap.cli.init
         refs:
           - path: src/core/init.ts
             line_start: 1
     ```
   - Map incrementally — one domain at a time
   - Run `openspec bootstrap status` to track per-domain progress
   - Run `openspec bootstrap validate` after all domains mapped

   **Phase: review**
   - Validate regenerates review.md and candidate OPSX files from current `evidence.yaml` and `domain-map/*.yaml`
   - Review each domain checkbox in review.md
   - Check all validation checkboxes
   - If evidence or domain maps change, rerun validate and re-approve the regenerated review
   - Low-confidence domains appear first for priority review

   **Phase: promote**
   ```bash
   openspec bootstrap promote -y
   ```
   Re-validates all upstream gates before writing.
   - `opsx-first`: writes the formal OPSX three-file bundle plus only `openspec/specs/README.md`
   - `full` on `raw`: writes the formal OPSX bundle plus one validated spec per mapped capability
   - `full` on `specs-based`: preserves existing specs, adds only missing capability specs, and fails fast on target-path conflicts
   Retains the bootstrap workspace on success so you can inspect or delete it manually later.

3. **After each phase action**
   - Run `openspec bootstrap validate` to verify gate conditions
   - Run `openspec bootstrap status` to confirm phase advancement
   - Continue to next phase

**Evidence Guidelines**
- Use repository evidence only — do not fabricate
- Attach confidence levels: high (multiple sources), medium (single source), low (inferred)
- Prefer fewer domains with solid evidence over exhaustive noise
- Each domain should map to a clear architectural boundary

**Mapping Guidelines**
- Capability IDs follow `cap.<domain>.<action>` convention
- Code references must point to existing files
- Relations capture structural ownership (contains) and runtime dependencies (depends_on)
- Mark uncertain mappings for review attention

**Guardrails**
- Do NOT write directly to formal OPSX files — use the bootstrap workspace
- Do NOT fabricate code references
- Do NOT skip the review phase
- Do NOT treat stale review.md checkboxes as approval after evidence or mappings change
- Keep the graph small enough to audit in one sitting
