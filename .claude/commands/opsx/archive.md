---
name: "OPSX: Archive"
description: Archive a completed change in the experimental workflow
category: Workflow
tags: [workflow, archive, experimental]
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name after `/opsx:archive` (e.g., `/opsx:archive add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

When archive guidance discusses embedded sync, artifact write-back, or git archive policy, treat `openspec/config.yaml` as the compact source of truth and follow the shared prompt/runtime projection contract rather than reinterpreting raw config keys inside the template body. Archive consumes `git.merge.strategy`, `git.merge.messageFrom`, and `git.branch.deleteAfterArchive` from the compiled prompt projection; do not parse raw YAML inside the skill.

**Steps**

1. **If no change name provided, prompt for selection**

   Run `openspec list --json` to get available changes. Use the **AskUserQuestion tool** to let the user select.

   Show only active changes (not already archived).
   Include the schema used for each change if available.

   **IMPORTANT**: Do NOT guess or auto-select a change. Always let the user choose.

2. **Unified Full Verify Gate**

   Run the CLI gate:
   ```bash
   openspec verify status "<change-name>" --json
   ```

**Verify Result Freshness Rules**:

A verify result is considered **FRESH** if ALL of the following hold:
- `.verify-result.json` exists in the change directory
- `verificationContext.evidenceFingerprint` matches the current workspace fingerprint
- `verificationContext.contractVersion` is `"1.0"`
- `result` is `PASS` or `PASS_WITH_WARNINGS`

A verify result is considered **STALE** if ANY of the following hold:
- `verificationContext.evidenceFiles` is missing or the file list changed
- `verificationContext.evidenceFingerprint` does not match the recomputed fingerprint
- `verificationContext.gitHeadCommit` does not match the current HEAD (if recorded)
- `verificationContext.contractVersion` is missing or not `"1.0"`
- `result` is not `PASS` or `PASS_WITH_WARNINGS`

**Optimization metadata compatibility**:
- `optimization` metadata is advisory for archive gating, not part of the freshness hash inputs
- Legacy verify results without `optimization` may still be fresh if every freshness rule above passes
- If `optimization.status` exists, evaluate its acceptability separately from freshness

**When verify result is STALE or MISSING**:
- Archive MUST execute full verify before continuing
- Do NOT attempt to repair or reuse a stale verify result

**Fingerprint Computation**:
- Sort `evidenceFiles` alphabetically before hashing
- For each evidence file, collect normalized relative POSIX path + content hash
- Hash the JSON-serialized entries with SHA-256
- Use `path.join()`, `path.resolve()`, and `path.normalize()` for all path handling
- Persist `evidenceFiles` as relative POSIX paths for cross-platform comparison

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

**Verify CLI JSON Schema Reference**:

| CLI call | `--input` JSON |
| --- | --- |
| `openspec verify phase1 "<change-name>" --input '<json>' --json` | `{"result":"PASS","issues":[],"evidenceFiles":["..."],"executionMode":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"NO_OPTIMIZATION_NEEDED","summary":"..."}` (summary is required, must be non-empty) |
| `openspec verify phase2 "<change-name>" --type=optimization --files "<affected-files>" --input '<json>' --json` | `{"status":"OPTIMIZATION_PROPOSED","summary":"..."}` |
| `openspec verify phase2 "<change-name>" --type=optimization --input '<json>' --json` | `{"status":"SKIPPED"}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"PASS","issues":[]}` |
| `openspec verify phase2 "<change-name>" --type=verification --input '<json>' --json` | `{"result":"FAIL_NEEDS_REMEDIATION","issues":[...],"behaviorRetryCounter":N}` |

   - If the command exits 0, treat the persisted `.verify-result.json` as fresh and archive-compatible, then continue to Step 3
   - If the command exits non-zero because the result is MISSING or STALE, execute the full verify contract in Step 2.5 and then rerun `openspec verify status "<change-name>" --json`
   - If `result === 'FAIL_NEEDS_REMEDIATION'`, HARD-BLOCK archive, display CRITICAL issues from `issues[]`, and instruct the user to fix remediation items before rerunning verify
   - **If `optimization.status` is `PENDING_VERIFICATION`** — do NOT stop. Follow the recovery table below to resolve the incomplete state:

     | 子状态 | 恢复路径 |
     |--------|---------|
     | `PENDING_VERIFICATION` 且 **无** `affectedFileHashes` (或为空) | Phase 1 刚完成，尚未进入 Phase 2。Agent 应判断变更复杂度：若为简单变更（纯删除/重命名/参数移除），直接调用 `openspec verify phase2 "<name>" --type=optimization --input '{"status":"NO_OPTIMIZATION_NEEDED"}' --json`。否则执行 Phase 2 优化分析后调用同命令。完成后 `optimization.status` 变为 `NOT_NEEDED`，archive 门禁通过 |
     | `PENDING_VERIFICATION` 且 **有** `affectedFileHashes` | 优化提案已生成，等待验证确认。先执行 verification：`openspec verify phase2 "<name>" --type=verification --input '{"result":"PASS","issues":[]}' --json`。完成后 `optimization.status` 变为 `IMPROVED` 或 `DEGRADED`，archive 门禁通过 |

     After resolving `PENDING_VERIFICATION`, re-run `openspec verify status "<change-name>" --json` to confirm the gate passes.
   - **If `optimization.status` is `ABORTED_UNSAFE`** — HARD STOP. 工作区状态不安全，需人工恢复。不提供自动恢复路径

2.5. **Execute Full Verify**

   When the verify result is missing or stale, execute the same verify contract as `/opsx:verify` using the `subagent-orchestrated` skeleton:
   - Determine `changeName`, absolute `changeDir`, and absolute `projectRoot`
   - Spawn the reviewer subagent with Read and Bash tool capability, instruct it to invoke the `openspec-reviewer` skill for canonical Phase 1, and pass only `changeName`, `changeDir`, and `projectRoot`
   - Validate the reviewer payload, apply only deterministic `tasks.md` write-back in the main workspace, and persist the canonical Phase 1 payload
   - Execute the verify workflow end-to-end, including Phase 2 (spawn optimizer subagent with Read and Bash tool capability, invoke `openspec-optimizer`, and pass only `changeName`, `changeDir`, and `projectRoot`) whenever the `/opsx:verify` contract would make it eligible
   - In `P1_SPECULATIVE_FENCE`, invoke the reviewer subagent again with `changeName`, `changeDir`, and `projectRoot` for the speculative verdict
   - The top-level archive flow MUST NOT inline a current-agent review skeleton or silently downgrade to reread mode
   - If the canonical Phase 1 `result` is `PASS` or `PASS_WITH_WARNINGS`, and optimization is not disabled by config or an explicit `--skip-optimization` request, archive-time full verify MUST continue into Phase 2
   - Archive-time caution about speculative edits is NOT a valid reason to downgrade the run into a Phase-1-only verify
   - `optimization.status = 'SKIPPED'` is only valid when config disables optimization or the user explicitly requested `--skip-optimization`
   - Persist a fresh `.verify-result.json` before returning to archive
   - In `core`, this verify contract is embedded inside archive because there is no standalone verify surface
   - In `expanded`, you MAY invoke `/opsx:verify` or execute the same contract inline, but the semantics MUST stay identical

   **Important**:
   - This is the ONLY verify gate for archive
   - There is no archive-only mini check
   - There is no bypass path after a failed verify
   - `core` and `expanded` modes use the same archive gate logic

3. **Check artifact completion status**

   Run `openspec status --change "<name>" --json` to check artifact completion.

   Parse the JSON to understand:
   - `schemaName`: The workflow being used
   - `artifacts`: List of artifacts with their status (`done` or other)

   **If any artifacts are not `done`**:
   - Display warning listing incomplete artifacts
   - Use the **AskUserQuestion tool** to confirm the user wants to proceed
   - Proceed only if the user confirms

4. **Check task completion status**

   Read the tasks file (typically `tasks.md`) to check for incomplete tasks.

   Count tasks marked with `- [ ]` (incomplete) vs `- [x]` (complete).

   **If incomplete tasks are found**:
   - Display a warning showing the count of incomplete tasks
   - Use the **AskUserQuestion tool** to confirm the user wants to proceed
   - Proceed only if the user confirms

   **If no tasks file exists**: proceed without task-related warning.

5. **Assess delta sync state**

   Check for delta specs at `openspec/changes/<name>/specs/` and for `openspec/changes/<name>/opsx-delta.yaml`. If neither exists, proceed directly to archive.

   **If any delta exists**:
   - Run `openspec sync "<change-name>"` before archive so standalone sync and archive consume the same verify gate and sync contract
   - Abort archive if `openspec sync` fails, leaving main specs, OPSX files, and the active change directory unchanged
   - In `expanded`, `/opsx:sync` may still exist as a standalone workflow, but archive MUST follow the same sync-state contract

6. **Perform the archive**

   Create the archive directory if it does not exist:
   ```bash
   mkdir -p openspec/changes/archive
   ```

   Generate the target name using the current date: `YYYY-MM-DD-<change-name>`

   **Check if the target already exists**:
   - If yes: fail with an error and suggest renaming or removing the existing archive entry
   - If no: move the change directory to archive

   ```bash
   mv openspec/changes/<name> openspec/changes/archive/YYYY-MM-DD-<name>
   ```

7. **Create archive commit**

   After moving the change directory, create an archive commit on the current feature branch.

   Use the fixed docs-style archive commit message. Artifact-generated messages apply only to later merge commits, not to this archive commit.

   ```bash
   git add -- <archive-dir> <synced-spec-paths> <synced-opsx-paths>
   git commit -F -
   ```

   Record the archive commit SHA with `git rev-parse HEAD`.

   If `git.merge.messageFrom: manual`, write the generated message to `.merge-message.draft`, skip automatic merge, and report that manual merge is required.

8. **Merge archived branch**

   Read merge behavior from the compiled prompt projection:
   - `git.merge.strategy`: `no-ff`, `ff-only`, or `squash`
   - `git.merge.messageFrom`: `artifacts` or `manual`
   - `git.branch.deleteAfterArchive`: `true` or `false`

   Do not parse raw YAML inside the skill.

   Merge only after Step 7 has an archive commit and automatic merge is not skipped.

   For `git.merge.strategy: no-ff`:
   ```bash
   git checkout <original-branch>
   git merge --no-ff --no-commit <feature-branch>
   git commit -F -
   ```

   For `git.merge.strategy: ff-only`:
   ```bash
   git checkout <original-branch>
   git merge --ff-only <feature-branch>
   ```

   For `git.merge.strategy: squash`:
   ```bash
   git checkout <original-branch>
   git merge --squash <feature-branch>
   git commit -F -
   ```

   If merge conflicts occur, run:
   ```bash
   git merge --abort
   ```

   Preserve the archive commit on the feature branch and report the recovery command. Record the merge SHA with `git rev-parse HEAD` when merge succeeds, or record the abort status when it fails.

9. **Cleanup feature branch and worktree**

   Read `openspec/changes/archive/YYYY-MM-DD-<name>/.apply-isolation.json` after the change directory moves.

   **If no isolation file exists or `originalBranch` is empty**: resolve the original branch using `git symbolic-ref refs/remotes/origin/HEAD --short`; if that fails, ask for the original branch name and persist it in `.apply-isolation.json`.

   **If originalBranch cannot be resolved**: skip merge and branch cleanup, leave the current branch unchanged, and continue to summary.

   **If `method === "worktree"` and `worktreePath` exists**:
   - Ask: "Delete worktree directory <path>?"
   - If confirmed, run `git worktree remove <path>`
   - If declined, leave the worktree untouched and mention it in the summary

   **If `originalBranch` exists**:
   - Ask: "Switch back to original branch <originalBranch>?"
   - If confirmed, run `git checkout <originalBranch>`
   - If declined, leave the current branch unchanged and mention it in the summary

   **If `git.branch.deleteAfterArchive: true` and the merge strategy is not `squash`**:
   - Confirm the branch is merged with `git branch --merged`
   - If confirmed, run `git branch -d <feature-branch>`
   - If not merged, keep the branch and mention it in the summary

   **If `git.branch.deleteAfterArchive: false` or merge strategy is `squash`**: keep the feature branch and mention it in the summary.

   **Important**:
   - Do not silently delete worktrees.
   - Do not silently switch branches.
   - Build paths with `path.join()`, `path.resolve()`, and `path.normalize()`; display platform-native paths.

10. **Display summary**

   Show archive completion summary including:
   - Change name
   - Schema that was used
   - Archive location
   - Archive Commit SHA
   - Merge Strategy
   - Merge SHA / Status
   - Feature Branch
   - Whether specs / OPSX were synced (if applicable)
   - Whether a fresh verify result was reused or archive had to execute full verify
   - Whether apply isolation cleanup was skipped, declined, or completed
   - Any warnings about incomplete artifacts or tasks

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Verify Gate:** Fresh PASS or PASS_WITH_WARNINGS result confirmed
**Specs / OPSX:** ✓ Synced to main specs and project OPSX (or "No deltas" or "Skipped all archive-time sync writes")
**Archive Commit SHA:** <sha>
**Merge Strategy:** <git.merge.strategy>
**Merge SHA / Status:** <sha or skipped/manual/aborted>
**Feature Branch:** <deleted/kept/worktree kept/manual cleanup required>

Archive completed after satisfying the unified full verify gate.
```

**Guardrails**
- Always prompt for change selection if not provided
- Use artifact graph (`openspec status --json`) for completion checking
- Do not downgrade the verify gate into a lightweight archive-only check
- Preserve `.openspec.yaml` when moving to archive (it moves with the directory)
- Show clearly whether verify was reused or re-executed
- In `core`, use `openspec sync "<change-name>"` rather than manual inline sync
- If delta specs or `opsx-delta.yaml` exist, always run the shared sync assessment before moving the change directory
