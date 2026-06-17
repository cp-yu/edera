---
name: "openspec-apply-change"
description: "Implement tasks from an OpenSpec change. Use when the user wants to start implementing, continue implementation, or work through tasks."
license: "MIT"
compatibility: "Requires openspec CLI."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

Implement tasks from an OpenSpec change.

## Skill Delegation Protocol

**Internal Skills** — The following skills are subagent-only and MUST NOT be read directly by this agent:
- `openspec-impact-sweeper` — Use a subagent, not direct reading
- `openspec-reviewer` — Use a subagent, not direct reading
- `openspec-optimizer` — Use a subagent, not direct reading

**Never** use the Read tool on `.claude/skills/openspec-impact-sweeper/SKILL.md`, `.claude/skills/openspec-reviewer/SKILL.md`, or `.claude/skills/openspec-optimizer/SKILL.md`.

## Flow

1. Select the change. If no clear name is provided, infer only from explicit context; otherwise run `openspec list --json` and ask. Always announce "Using change: <name>".
2. Run `openspec status --change "<name>" --json` and `openspec instructions apply --change "<name>" --json`. Read `configProjection.prompt.fragments` for `proseLanguage` and `apply.defaultIsolation`. Handle `state: "needs_verify"` by skip back to Phase 1 and `state: "needs_seal"` by continue with Phase 2/3.
3. Load shared OPSX context before reading change artifacts.
Before reading other context files, check whether `openspec/project.opsx.yaml` exists.
- If it exists, read it first for domains → capabilities structure
- Read the `project:` block for project intent and scope
- Treat it as navigation context, not as a replacement for change artifacts
4. Read every context file listed by the CLI. Inspect `changeDir/.verify-result.json` and `## Remediation`; unresolved CRITICAL/code_fix/artifact_fix items take priority.
5. Use CLI-backed OPSX navigation after shared context.
After reading shared `project.opsx.yaml` context, use OpenSpec CLI query surfaces for node details.
- Run `openspec list --specs --json` to get specs and their `capabilities` string arrays; specs without frontmatter return `capabilities: []`.
- For known or affected OPSX node IDs, run `openspec opsx query <node-id...> --json` to get node details, relations and code-map refs in one batch; add `--depth 2` when broader related context is needed.
- Treat CLI output as navigation context, not as a replacement for change artifacts.

### Branch Isolation Preflight

Run `git branch --show-current`. On main/master ask whether to Create branch `<change-name>`, Create worktree at `.worktrees/<change-name>`, or continue; config branch/worktree/none use that as the default choice without prompting; only `ask` is interactive and means prompt. Persist `path.join(changeDir, '.apply-isolation.json')` with `method`, `branchName`, optional `worktreePath`, and `originalBranch`. Use using-git-worktrees when present.

### Master Agent Strict TDD Implementation

Execute tasks sequentially. For each pending task, read Goal, Files, Requirements, and Checks. For behavior or code Checks, add or update the targeted test before implementation. Run the declared Check command or equivalent targeted command and confirm the expected failure before implementation. Make the minimal implementation needed for that Check. Rerun the same or equivalent Check command and confirm pass before updating task or remediation checkboxes. Non-runtime text or artifact Checks do not require artificial red failures. Config, schema, template, workflow template, and agent instruction template Checks default to behavior/code Checks. Mark the task's nested Checks complete in `tasks.md` only after red/green evidence or final non-runtime evidence passes.

TDD Checkpoint 1: Interface Design for Testability — dependencies are injected through parameters, behavior returns values or observable results, and public interface area is minimal. TDD Checkpoint 2: Test Quality Standards — verifies behavior through public interfaces, avoids mocking internal project collaborators, keeps one logical assertion per test, and survives internal refactoring. TDD Checkpoint 3: Mock Boundary Enforcement — mocks are allowed only at system boundaries; internal classes, modules, and project-owned collaborators MUST NOT be mocked; mockable boundaries must be passed through dependency injection.

### Continuous Recovery Protocol

Failures are recovery feedback. Normalize as `task + check + command + failure kind`; pause only after two consecutive failures for the same task and same normalized error signature. A changed normalized error signature is progress. If a task Goal or Requirements is ambiguous, enrich context from proposal, design, change-local specs, tasks.md, OPSX code-map, related specs, and project search. If project context is missing, convert the gap into verifiable exploration or check steps in the current task and continue execution. Phase 1 failures enter the same recovery loop. User interrupt remains an immediate stop condition.

### Phase 1: Run canonical verification

Invoke reviewer subagent, persist `openspec verify phase1 "<change-name>" --input '<json>' --json`, and write back only CRITICAL remediation.

### Phase 2: Optimize under checkpoint protection

You MUST read `openspec/references/openspec-apply-phase2-optimization.md` before Phase 2. Checkpoints are git commits, not git stash entries or git tags. Respect `--skip-optimization`; read `optimization.optRetries`; create the initial checkpoint commit with `git add -A && git commit -m "wip: opt-checkpoint-r0 (baseline)"`; invoke Optimizer subagent; use `openspec verify phase2`; create an incremental checkpoint commit for each successful optimization round; record each failed direction.

### Phase 3: Seal final result

Run `openspec verify seal "<change-name>" --json`. If seal fails, preserve diagnostics, convert them into remediation context, map the remediation to the affected task, and return to Phase 0 recovery. Do not pause on the first seal failure.

**Verify CLI JSON Schema Reference**:

| CLI call | `--input` JSON |
| --- | --- |
| `openspec verify phase1 "<change-name>" --input '<json>' --json` | `{"result":"PASS","issues":[],"evidenceFiles":["..."],"executionMode":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"NO_OPTIMIZATION_NEEDED","summary":"..."}` (summary is required, must be non-empty) |
| `openspec verify phase2 "<change-name>" --type=optimization --files "<affected-files>" --input '<json>' --json` | `{"status":"OPTIMIZATION_PROPOSED","summary":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"SKIPPED"}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"PASS","issues":[]}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"FAIL_NEEDS_REMEDIATION","issues":[...],"behaviorRetryCounter":N}` |
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

## Output

Report schema, progress, current task, completed tasks this session, and final sealed/archive-ready status. Keep edits minimal, use Node path handling for generated paths, update task checkboxes only after evidence passes, and preserve canonical artifact headings/tokens and configured document language projection.
