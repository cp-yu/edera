---
name: "OPSX: Propose"
description: Propose a new change - create it and generate all artifacts in one step
category: Workflow
tags: [workflow, artifacts, experimental]
---

Propose a new change - create the change and generate all artifacts in one step.

I'll create a change with artifacts:
- proposal.md (what & why)
- design.md (how)
- tasks.md (implementation steps)
- opsx-delta.yaml (project OPSX delta, generated after specs are clear)

When ready to implement, run /opsx:apply

---

**Input**: The argument after `/opsx:propose` is the change name (kebab-case), OR a description of what the user wants to build.

**Steps**

1. **If no input provided, ask what they want to build**

   Use the **AskUserQuestion tool** (open-ended, no preset options) to ask:
   > "What change do you want to work on? Describe what you want to build or fix."

   From their description, derive a kebab-case name (e.g., "add user authentication" → `add-user-auth`).

   **IMPORTANT**: Do NOT proceed without understanding what the user wants to build.

## Smart Explore Routing

Before creating artifacts, inspect the current conversation for an explore-generated `Design Summary`.

- If a Design Summary exists, extract architecture, core components, data flow, technology stack, testing strategy, and risks/trade-offs. Use those sections as primary input for proposal.md, design.md, specs, and coarse tasks.
- If no Design Summary exists, read `openspec/config.yaml` through the compiled config projection. When `propose.smartRouting: false` or `propose.requireExplore: false` is configured, keep legacy behavior and proceed directly.
- Otherwise, score the user's input across 5 dimensions: technology stack/library, data model/interface, API endpoint/function signature, test strategy, boundary conditions/error handling.
- Treat input as detailed only when length is greater than 100 characters and score is at least 3/5.
- Detect multi-subsystem scope when the input uses broad platform/system wording or lists more than 3 parallel modules joined by terms like "包含", "以及", "和", commas, or enumeration.

Routing outcomes:
- Design Summary found: proceed and show that Design Summary is being used.
- Detailed input: proceed and show "输入足够详细，跳过 explore，直接生成制品。"
- Multi-subsystem input: stop and show "这个需求涉及多个独立子系统，建议先运行 `/opsx:explore` 进行拆解。"
- Simple input: stop and show "输入过于简单，建议先运行 `/opsx:explore` 澄清需求和设计方案。"

Decision transparency:
- Show input length, detail score, multi-subsystem result, and final decision.
- If proceeding, add a proposal.md HTML comment recording the same decision.
- If recommending explore, allow the user to explicitly override by saying the input is sufficient and they want direct artifact generation.

Tasks output:
- Generate coarse `tasks.md` with `### Task N:`, `Goal`, `Files`, `Requirements`, and nested `Checks`.
- Use one task per core component when using a Design Summary.
- Keep each task to 5 or fewer Requirements and split larger components.

2. **Create the change directory**
   ```bash
   openspec new change "<name>"
   ```
   This creates a scaffolded change at `openspec/changes/<name>/` with `.openspec.yaml`.

3. **Get the artifact build order**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to get:
   - `applyRequires`: array of artifact IDs needed before implementation (e.g., `["tasks"]`)
   - `artifacts`: list of all artifacts with their status and dependencies

Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Check `openspec/project.opsx.code-map.yaml` for code location references
- Check `openspec/specs/` for behavior documentation
- Treat it as navigation context, not as a replacement for change artifacts

4. **Create artifacts in sequence until apply-ready**

   Use the **TodoWrite tool** to track progress through the artifacts.

   Loop through artifacts in dependency order (artifacts with no pending dependencies first):

   a. **For each artifact that is `ready` (dependencies satisfied)**:
      - Get instructions:
        ```bash
        openspec instructions <artifact-id> --change "<name>" --json
        ```
      - The instructions JSON includes:
        - `context`: Project background (constraints for you - do NOT include in output)
        - `rules`: Artifact-specific rules (constraints for you - do NOT include in output)
        - `template`: The structure to use for your output file
        - `instruction`: Schema-specific guidance for this artifact type
        - `outputPath`: Where to write the artifact
        - `dependencies`: Completed artifacts to read for context
      - Read any completed dependency files for context
      - Create the artifact file using `template` as the structure
      - Apply `context` and `rules` as constraints - but do NOT copy them into the file
      - Show brief progress: "Created <artifact-id>"

   b. **Continue until all `applyRequires` artifacts are complete**
      - After creating each artifact, re-run `openspec status --change "<name>" --json`
      - Check if every artifact ID in `applyRequires` has `status: "done"` in the artifacts array
      - Stop when all `applyRequires` artifacts are done

   c. **If an artifact requires user input** (unclear context):
      - Use **AskUserQuestion tool** to clarify
      - Then continue with creation

   d. **After the `specs` artifact is complete in a spec-driven change, generate `opsx-delta.yaml`**
      **Generate opsx-delta.yaml**:
- Read `openspec instructions opsx-delta --change "<name>" --json`
- Use the returned `template`, `instruction`, and `outputPath` to generate `opsx-delta.yaml`
- Read `proposal.md` to extract the capability list
- Read all delta specs in `openspec/changes/<name>/specs/*/spec.md`
- Read `openspec/project.opsx.yaml` if it exists for current-system context
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

5. **Run post-propose validation before the final summary**

   **Run post-propose warning validation**:
- This validation is warning-only. Do NOT turn `/opsx:propose` into a blocking gate.
- Validate generated change specs against the same contract used by downstream change delta validation:
  - Prefer `openspec validate "<name>" --type change --json` when available
  - Align with `Validator.validateChangeDeltaSpecs()` semantics for delta sections, SHALL/MUST requirement text, and required `#### Scenario:` blocks
- Validate `opsx-delta.yaml` through the same programmatic CLI path used by downstream change validation:
  - Prefer `openspec validate "<name>" --type change --json` when available
  - Align with `Validator.validateOpsxDelta()` semantics for Zod parsing, dry-run `applyOpsxDelta()`, referential integrity, and code-map integrity
  - Do NOT run `openspec sync` for this check because it mutates project files
  - If `openspec/project.opsx.yaml` does not exist, `Validator.validateOpsxDelta()` skips this check and the final summary must report the skip
- Run lightweight structure checks for `proposal.md`, `design.md`, and `tasks.md` against the current schema templates, not scattered examples:
  - Read `openspec instructions proposal --change "<name>" --json`, `openspec instructions design --change "<name>" --json`, and `openspec instructions tasks --change "<name>" --json`
  - Check only key required headings and checkbox structure
  - For `tasks.md`, run a deterministic task structure check equivalent to `validateTaskStructure` in `src/core/parsers/task-structure.ts`
  - Programmatically verify either legacy `Actions`/`Checks` sections or coarse `### Task N:` sections with `Goal`, `Files`, `Requirements`, and nested `Checks`
  - For legacy tasks, verify `A`-prefixed action checkboxes, `C`-prefixed check checkboxes, required `Covers:` fields, valid `Covers:` references, and every action covered by at least one check
  - For coarse tasks, verify each task has no more than 5 requirements and at least one nested `C`-prefixed check
  - For every check, verify required non-empty `Verifies:` fields, change-local `Verifies:` spec paths plus Requirement/Scenario references when local change specs exist, and at least one `Command:`, `Evidence:`, or `Expect:` field
  - Do NOT invent semantic lint rules beyond the current templates
  - Do NOT judge whether a check is semantically sufficient; defer semantic suitability to verify/reviewer
- If warnings are found, do exactly one repair pass on the generated artifacts, then re-check once
- Final summary MUST separate:
  - fixed warnings
  - remaining warnings
  - skipped checks
- Even with remaining warnings, you MAY still declare the change ready for `/opsx:apply`, but disclose the residual issues explicitly

6. **Show final status**
   ```bash
   openspec status --change "<name>"
   ```

**Output**

After completing all artifacts, summarize:
- Change name and location
- List of artifacts created with brief descriptions
- Validation summary with fixed warnings, remaining warnings, and skipped checks
- What's ready: "All artifacts created! Ready for implementation."
- Prompt: "Run `/opsx:apply` to start implementing."

**Artifact Creation Guidelines**

- Follow the `instruction` field from `openspec instructions` for each artifact type
- The schema defines what each artifact should contain - follow it
- Read dependency artifacts for context before creating new ones
- Use `template` as the structure for your output file - fill in its sections

**Document Language Contract**:
- Treat `openspec/config.yaml` as the compact source of truth, but consume its compiled prompt projection rather than reinterpreting raw keys ad hoc
- If the compiled projection includes `docLanguage`, apply it only to natural-language prose you write in the artifact body
- Follow the existing template structure exactly; do not invent a different layout because the prose language changes
- Keep template headings, IDs, schema keys, relation types, BDD keywords, file paths, commands, and code identifiers in their canonical form
- If no `docLanguage` projection is present, keep the default writing behavior for prose

- **IMPORTANT**: `context` and `rules` are constraints for YOU, not content for the file
  - Do NOT copy `<context>`, `<rules>`, `<project_context>` blocks into the artifact
  - These guide what you write, but should never appear in the output

**Guardrails**
- Create ALL artifacts needed for implementation (as defined by schema's `apply.requires`)
- Always read dependency artifacts before creating a new one
- If context is critically unclear, ask the user - but prefer making reasonable decisions to keep momentum
- If a change with that name already exists, ask if user wants to continue it or create a new one
- Verify each artifact file exists after writing before proceeding to next
