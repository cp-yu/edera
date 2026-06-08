---
name: openspec-archive-change
description: Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a completed change after implementation is complete.
license: MIT
compatibility: Requires openspec CLI.
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.2.0-cpyu.9"
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

Before archiving, run `openspec config project --json` and consume git policy from its normalized project config: `git.autoCommit`, `git.archive.commitMessage.convention`, `git.merge.strategy`, `git.merge.commitMessage.convention`, and `git.branch.deleteAfterArchive`; do not parse raw YAML inside the skill.

**Steps**

1. **Select change**
   If no clear change name is provided, run `openspec list --json`, show active changes with schema, and ask. Do not guess.

2. **Unified Full Verify Gate**
   Run `openspec verify status "<change-name>" --json`. Fresh PASS/PASS_WITH_WARNINGS continues. MISSING/STALE runs Step 2.5 then reruns the gate. FAIL_NEEDS_REMEDIATION hard-blocks with CRITICAL issues. Resolve `PENDING_VERIFICATION` through the appropriate `openspec verify phase2` optimization/verification call, then rerun status. `ABORTED_UNSAFE` hard-stops for manual recovery.

2.5. **Execute Full Verify**

   When the verify result is missing or stale, execute the same verify contract as `/opsx:verify` using the `subagent-orchestrated` skeleton:
   - Determine `changeName`, absolute `changeDir`, and absolute `projectRoot`
   - Spawn the reviewer subagent with Read and Bash tool capability, instruct it to invoke the `openspec-reviewer` skill for canonical Phase 1, and pass only `changeName`, `changeDir`, and `projectRoot`
   - Validate the reviewer payload, apply only deterministic `tasks.md` write-back in the main workspace, and persist the canonical Phase 1 payload
   - Execute the verify workflow end-to-end, including Phase 2 (spawn optimizer subagent with Read and Bash tool capability, invoke `openspec-optimizer`, and pass only `changeName`, `changeDir`, and `projectRoot`) whenever the `/opsx:verify` contract would make it eligible
   - In `P1_SPECULATIVE_FENCE`, invoke the reviewer subagent again with `changeName`, `changeDir`, and `projectRoot` for the speculative verdict
   - The top-level archive flow MUST NOT inline a current-agent review skeleton or silently downgrade to reread mode
   Continue through Phase 2 when eligible; `SKIPPED` is valid only for config/user skip. Persist fresh verify before archiving. This is the only archive gate; no mini-check or bypass exists.

3. **Check artifact completion status**
   Run `openspec status --change "<name>" --json`. Warn and confirm before proceeding if any artifact is not `done`.

4. **Check task completion status**
   Read `tasks.md`; warn and confirm before proceeding if incomplete checkboxes remain. Missing tasks are not a task-related blocker.

5. **Assess delta sync state**
   If delta specs or `opsx-delta.yaml` exist, run `openspec sync "<change-name>"`; abort on sync failure without moving the change.

6. **Perform the archive**
   Create `openspec/changes/archive`, fail if `YYYY-MM-DD-<change-name>` exists, then move the change directory there. Preserve `.openspec.yaml`.

7. **Create archive commit**
   If `git.autoCommit: manual`, skip archive commit, merge, and cleanup; report manual status and leave the moved/synced files in the worktree. Otherwise add only the archive/synced paths and run `git commit -F -` with the fixed docs-style archive message using `git.archive.commitMessage.convention`. Record `git rev-parse HEAD`.

8. **Merge archived branch**
   After Step 7, apply the compiled merge strategy: `git merge --no-ff --no-commit` then `git commit -F -`, or `git merge --ff-only`, or `git merge --squash` then `git commit -F -`. Use `git.merge.commitMessage.convention` for merge/squash commit messages. On conflicts run `git merge --abort`, preserve the archive commit, and report recovery. Record merge SHA/status.

9. **Cleanup feature branch and worktree**
   Read archived `.apply-isolation.json`. Resolve missing `originalBranch` with `git symbolic-ref refs/remotes/origin/HEAD --short` or ask. Never silently remove worktrees or switch branches. If deletion is enabled and non-squash, confirm merged with `git branch --merged` before branch deletion. Build paths with `path.join()`, `path.resolve()`, and `path.normalize()`.

10. **Display summary**
   Include change, schema, archive location, Archive Commit SHA, Merge Strategy, Merge SHA / Status, Feature Branch, sync status, verify reuse/reexecution, cleanup status, and warnings.

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Verify Gate:** Fresh PASS or PASS_WITH_WARNINGS result confirmed
**Specs / OPSX:** ✓ Synced to main specs and project OPSX (or "No deltas" or "Skipped all archive-time sync writes")
**Archive Commit SHA:** <sha>
**Auto Commit:** <git.autoCommit>
**Merge Strategy:** <git.merge.strategy>
**Merge SHA / Status:** <sha or skipped/manual/aborted>
**Feature Branch:** <deleted/kept/worktree kept/manual cleanup required>

Archive completed after satisfying the unified full verify gate.
```

**Guardrails**
- Always prompt for change selection if not provided
- Do not downgrade the verify gate into a lightweight archive-only check
- Show clearly whether verify was reused or re-executed
- In `core`, use `openspec sync "<change-name>"` rather than manual inline sync
- If delta specs or `opsx-delta.yaml` exist, always run the shared sync assessment before moving the change directory
