---
name: "OPSX: Apply"
description: Implement tasks from an OpenSpec change (Experimental)
category: Workflow
tags: [workflow, artifacts, experimental]
---

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name (e.g., `/opsx:apply add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: <name>" and how to override (e.g., `/opsx:apply <other>`).

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

3. **Get apply instructions**

   ```bash
   openspec instructions apply --change "<name>" --json
   ```

   This returns:
   - Context file paths (varies by schema)
   - Progress (total, complete, remaining)
   - Task list with status
   - Dynamic instruction based on current state

   **Handle states:**
   - If `state: "blocked"` (missing artifacts): show message, suggest using `/opsx:continue`
   - If `state: "needs_verify"`: skip back to Phase 1 and run canonical verification
   - If `state: "needs_seal"`: skip implementation and continue with Phase 2/3
   - If `state: "all_done"`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Read context files**

   Use OpenSpec CLI query surfaces for architecture context instead of reading OPSX YAML files directly.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id> --json` to get node details, relations, and code-map refs.
- Treat CLI output as navigation context, not as a replacement for change artifacts.

   Read the files listed in `contextFiles` from the apply instructions output.
   The files depend on the schema being used:
   - **spec-driven**: proposal, specs, design, tasks
   - Other schemas: follow the contextFiles from CLI output
   - Build `path.join(changeDir, '.verify-result.json')` and check whether the previous verify result exists
   - Read `.verify-result.json` defensively: newer results may include an `optimization` object in addition to `result`, `issues`, and `verificationContext`
   - If the file exists and `result === 'FAIL_NEEDS_REMEDIATION'`:
     - Read the persisted `issues` array
     - Keep only CRITICAL issues as mandatory remediation context
   - If `optimization.status` is `DEGRADED` or `ABORTED_UNSAFE`, treat it as advisory context only; do NOT let it override the canonical Phase 1 remediation signal
   - If `tasks.md` contains a `## Remediation` section:
     - Parse each checkbox item
     - Track whether the item is tagged `[code_fix]` or `[artifact_fix]`
     - Treat unchecked remediation items as priority work

**Document Language Contract**:
- Treat `openspec/config.yaml` as the compact source of truth, but consume its compiled prompt projection rather than reinterpreting raw keys ad hoc
- If the compiled projection includes `docLanguage`, apply it only to natural-language prose you write in the artifact body
- Follow the existing template structure exactly; do not invent a different layout because the prose language changes
- Keep template headings, IDs, schema keys, relation types, BDD keywords, file paths, commands, and code identifiers in their canonical form
- If no `docLanguage` projection is present, keep the default writing behavior for prose

5. **Show current progress**

   Display:
   - Schema being used
   - Progress: "N/M tasks complete"
   - Remaining tasks overview
   - Summary of prior CRITICAL verify issues when `.verify-result.json` reports `FAIL_NEEDS_REMEDIATION`
   - Summary of open remediation items grouped by `[code_fix]` and `[artifact_fix]`
   - Dynamic instruction from CLI

6. **Phase 0: Implement tasks (loop until done or blocked)**

### Branch Isolation Preflight

Before Phase 0 implementation:
- Run `git branch --show-current`.
- If the branch is `main` or `master`, warn that apply will create frequent commits and ask for one isolation choice:
  1. Create branch `<change-name>`
  2. Create worktree at `.worktrees/<change-name>`
  3. Continue on current branch after explicit confirmation
- If `openspec/config.yaml` sets `apply.defaultIsolation` to `branch`, `worktree`, or `none`, use that as the default choice without prompting; only `ask` is interactive and means prompt.
- Persist the result in `path.join(changeDir, '.apply-isolation.json')`:
  ```json
  {
    "method": "branch | worktree | none",
    "branchName": "<branch-name>",
    "worktreePath": "<path when worktree>",
    "originalBranch": "<original-branch-name>"
  }
  ```
- For worktrees, first check `.claude/skills/using-git-worktrees/` and `skills/using-git-worktrees/`. Use that skill when present; otherwise use `git worktree add` with paths built through `path.join()`.

### Master Agent Strict TDD Implementation

For each pending coarse task:
- Read Goal, Files, Requirements, and Checks from `tasks.md`.
- Explore project context by reading listed files, nearby existing patterns, related tests, and relevant specs/design.
- Before implementing a capability, run `openspec list --specs --json`, build the cap→spec mapping from each spec's `capabilities` string array, read every spec linked to the affected cap, and confirm whether the change-local delta spec must be updated. Specs without frontmatter return `capabilities: []`.
- **TDD Checkpoint 1: Interface Design for Testability** — Before writing tests, evaluate whether dependencies are injected through parameters, behavior returns values or observable results instead of hidden side effects, and the public interface area is minimal. If the target interface violates these principles, adjust the interface design before continuing instead of forcing tests around untestable code.
- For behavior or code Checks, add or update the targeted test before implementation.
- **TDD Checkpoint 2: Test Quality Standards** — Before entering RED, confirm each test verifies behavior through public interfaces, avoids mocking internal project collaborators, keeps one logical assertion per test, and survives internal refactoring because it depends on behavior rather than implementation details. Rewrite tests that fail these standards before running the RED check.
- Run the declared Check command or equivalent targeted command and confirm the expected failure before implementation.
- Make the minimal implementation needed for that Check. **TDD Checkpoint 3: Mock Boundary Enforcement** applies during implementation: mocks are allowed only at system boundaries such as external APIs, databases, time sources, or the file system; internal classes, modules, and project-owned collaborators MUST NOT be mocked; mockable boundaries must be passed through dependency injection. If implementation appears to require an internal mock, stop and refactor the interface to accept the dependency before continuing.
- Rerun the same or equivalent Check command and confirm pass before updating task or remediation checkboxes.
- Non-runtime text or artifact Checks do not require artificial red failures.
- For non-runtime text or artifact Checks, run the declared verification command or inspect the declared `Evidence:` / `Expect:` fields.
- Config, schema, template, workflow template, and agent instruction template Checks default to behavior/code Checks unless the Check explicitly establishes there is no runtime or generated-surface consumer.
- Keep generated commands and file paths cross-platform; use Node.js path handling when constructing paths.
- Mark the task's nested Checks complete in `tasks.md` only after red/green evidence or final non-runtime evidence passes.

### Continuous Recovery Protocol

- Failures are recovery feedback, not immediate user-visible pause conditions.
- Normalize each failure as `task + check + command + failure kind`; do not compare full natural-language output.
- Track retries per same task and same normalized error signature after master remediation.
- Pause only when the same task and same normalized error signature produces two consecutive failures after master remediation.
- A changed normalized error signature is progress: reset the previous signature's consecutive failure count and continue the recovery loop.
- If a task Goal or Requirements is ambiguous, enrich context from proposal, design, change-local specs, tasks.md, OPSX code-map, related specs, and project search before asking the user.
- If project context is missing, convert the gap into verifiable exploration or check steps in the current task and continue execution.
- Phase 1 failures enter the same recovery loop: write CRITICAL issues to `tasks.md`, add typed remediation, map the remediation to affected tasks, and continue Phase 0.
- Seal failures enter the same recovery loop: preserve diagnostics, convert them into remediation context, map the remediation to affected tasks, and continue Phase 0.
- User interrupt remains an immediate stop condition.

   For each pending task:
   - Show which task is being implemented
   - If the task was unmarked by verify, inject the matching CRITICAL issue and remediation item into the working context before editing files
   - Prioritize unchecked remediation entries before unrelated polish work
   - For `[code_fix]` remediation items, update code/tests until the missing behavior is implemented
   - For `[artifact_fix]` remediation items, update the affected spec/design/tasks artifact instead of forcing code changes
   - Keep changes minimal and focused
   - Mark task nested checks complete in the tasks file after implementation evidence passes
   - Mark resolved remediation items complete in the `## Remediation` section
   - Continue to next task

   **Pause if:**
   - Task remains unclear after reading proposal, design, change-local specs, tasks, OPSX code-map, related specs, and nearby project files
   - Implementation reveals a requirements scope change that cannot be represented as local artifact or task remediation
   - The same task and same normalized error signature reaches the Continuous Recovery Protocol pause threshold
   - User interrupts

7. **Phase 1: Run canonical verification**

   After all implementation tasks and remediation items are complete:
   - Spawn a clean-context reviewer subagent with change artifacts, git evidence, final file contents, and prior `.verify-result.json` when present
   - Instruct the subagent to invoke the `openspec-reviewer` skill, which loads the full reviewer contract (role, constraints, 6-step verification protocol, severity thresholds, three-dimension coverage, structured output schema)
   - Keep completeness, correctness, and coherence judgment inside the reviewer subagent
   - If the reviewer returns `FAIL_NEEDS_REMEDIATION`, write back only CRITICAL issues to `tasks.md`, add typed `## Remediation` entries, and return to Phase 0
   - If the reviewer returns `PASS` or `PASS_WITH_WARNINGS`, persist Phase 1:
     ```bash
     openspec verify phase1 "<change-name>" --input '<json>' --json
     ```

**Verify CLI JSON Schema Reference**:

| CLI call | `--input` JSON |
| --- | --- |
| `openspec verify phase1 "<change-name>" --input '<json>' --json` | `{"result":"PASS","issues":[],"evidenceFiles":["..."],"executionMode":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"NO_OPTIMIZATION_NEEDED","summary":"..."}` (summary is required, must be non-empty) |
| `openspec verify phase2 "<change-name>" --type=optimization --files "<affected-files>" --input '<json>' --json` | `{"status":"OPTIMIZATION_PROPOSED","summary":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"SKIPPED"}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"PASS","issues":[]}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"FAIL_NEEDS_REMEDIATION","issues":[...],"behaviorRetryCounter":N}` |

8. **Phase 2: Optimize under checkpoint protection**

   **Role constraint**: The master agent is an evidence collector and patch applicator in Phase 2. It MUST NOT substitute its own judgment for the optimizer subagent's decision on whether optimization is needed. Always spawn the optimizer subagent as the first action in Phase 2.

   - Skip Phase 2 only when the user requested `--skip-optimization` or `optimization.enabled: false`; record `SKIPPED` through `openspec verify phase2`
   - Read `optimization.optRetries` from `openspec/config.yaml`; default to `2`
   - Before the first optimization attempt, create a checkpoint: `git stash push -u -m "apply-opt-checkpoint-r0"`
   - Each complete proposal + patch + reviewer re-verify loop consumes one `optRetries` budget, whether it passes or fails
   - Format or Search/Replace matching problems are handled by the main agent and do not consume retry budget
   - Optimizer subagent: spawn and instruct to invoke the `openspec-optimizer` skill (loads full optimizer contract: role, constraints, optimization principles, Search/Replace format, failed directions protocol). Proposes Search/Replace blocks only; it MUST NOT edit files
   - **TIMING CONSTRAINT — hashFiles() samples disk state; the following order is mandatory:**
     1. Main agent calls `openspec verify phase2 "<change-name>" --type=optimization --files "<affected-files>" --input '<json>'` to record `OPTIMIZATION_PROPOSED` with pre-patch file hashes (disk MUST still be in pre-patch state at this point)
     2. Main agent applies Search/Replace blocks atomically (disk transitions to post-patch state)
     3. Main agent spawns the reviewer subagent for speculative Phase 1 re-verification
   - On speculative PASS, record `verification PASS`, and continue until no opportunities remain or `optRetries` is exhausted
   - On speculative FAIL, restore the latest checkpoint with `git reset --hard HEAD`, `git clean -fd`, then `git stash apply stash@{0}`; record the failed direction in `.verify-result.json`
   - When all attempts finish, consume all `apply-opt-checkpoint-*` stash entries only after the final safe workspace state is confirmed

**Simple Change Fast Path**:
- You MUST spawn the optimizer subagent at least once for every change, including pure deletions, renames, or parameter removals
- The optimizer subagent (not the master agent) decides whether optimization opportunities exist
- If the optimizer subagent returns "No optimization opportunities found", record `NO_OPTIMIZATION_NEEDED` with the optimizer's conclusion as the `summary` field:
  ```bash
  openspec verify phase2 "<change-name>" --type=optimization --input '{"status":"NO_OPTIMIZATION_NEEDED","summary":"<optimizer conclusion>"}' --json
  ```
- The master agent MUST NOT self-determine that no optimization is needed without spawning the optimizer subagent
- The only conditions that bypass the optimizer subagent are: `--skip-optimization` flag or `optimization.enabled: false` in config

**Verify CLI Error Recovery Guide**:
- If the CLI says `Invalid JSON input`: re-check that `--input` is a JSON string, not a file path; `issues` must be an array and `evidenceFiles` must be an array of strings
- If the CLI says `status must be NO_OPTIMIZATION_NEEDED, OPTIMIZATION_PROPOSED, ABORTED_UNSAFE, or SKIPPED`: fix the `--input.status` value and confirm whether `optimization.status` already has `affectedFileHashes`
- If the CLI says `result must be PASS, PASS_WITH_WARNINGS, or FAIL_NEEDS_REMEDIATION`: fix the `--input.result` value and keep `issues` as an array when provided
- If the CLI says `尚未提交优化结果，请先调用 phase2 --type=optimization`: call `phase2 --type=optimization` before retrying verification
- If the CLI says `FILES_REQUIRED`: add `--files "<affected-files>"` with the space-separated list of files the optimizer subagent declared as affected, then retry the same command

**Verify State Machine**:
```
Phase 1 PASS / PASS_WITH_WARNINGS
  |
  v
PENDING_VERIFICATION
  |-- no affectedFileHashes --> Phase 2 optimization analysis
  |                              |-- NO_OPTIMIZATION_NEEDED --> NOT_NEEDED
  |                              |-- SKIPPED / optimization.enabled=false --> SKIPPED
  |-- affectedFileHashes ------> PENDING_VERIFICATION (optimization proposed)
                                 |-- verification PASS --> IMPROVED
                                 |-- verification FAIL_NEEDS_REMEDIATION --> retry or DEGRADED
                                 |-- retries exhausted --> DEGRADED

Archive gate accepts: SKIPPED | NOT_NEEDED | IMPROVED | DEGRADED
Archive gate rejects: PENDING_VERIFICATION | ABORTED_UNSAFE
```

9. **Phase 3: Seal final result**

   Run:
   ```bash
   openspec verify seal "<change-name>" --json
   ```

   If seal passes, report apply as complete with verified and optimized status. If seal fails, preserve diagnostics, convert them into remediation context, map the remediation to the affected task, and return to Phase 0 recovery. Do not pause on the first seal failure.

10. **On completion or pause, show status**

   Display:
   - Tasks completed this session
   - Overall progress: "N/M tasks complete"
   - If remediation items were resolved, report that Phase 1 must pass before archive
   - If all done: suggest archive
   - If paused: explain why and wait for guidance

**Output During Implementation**

```
## Implementing: <change-name> (schema: <schema-name>)

Working on task 3/7: <task description>
[...implementation happening...]
✓ Task complete

Working on task 4/7: <task description>
[...implementation happening...]
✓ Task complete
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete and sealed. You can archive this change with `/opsx:archive`.
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

**Guardrails**
- Keep going through tasks until done or blocked
- Always read context files before starting (from the apply instructions output)
- If task is ambiguous, enrich context before asking
- If implementation reveals issues, first attempt scoped artifact, test, or implementation remediation
- Keep code changes minimal and scoped to each task
- Update task checkbox immediately after completing each task
- Pause on user interrupt, requirements scope changes, or repeated identical task error signatures after remediation
- Use contextFiles from CLI output, don't assume specific file names

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly
