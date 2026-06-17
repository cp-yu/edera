---
name: "openspec-archive-change"
description: "Archive a completed change in the experimental workflow. Use when the user wants to finalize and archive a completed change after implementation is complete."
license: "MIT"
compatibility: "Requires openspec CLI."
metadata:
  author: "openspec"
  version: "1.0"
  generatedBy: "1.4.1-cpyu.1"
---

Archive a completed change in the experimental workflow.

**Input**: Optionally specify a change name. If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

Before archiving, run `openspec config project --json` and consume git policy from its normalized project config: `git.commitMessage.archive`, `git.commitMessage.merge`, `git.merge.strategy`, and `git.branch.deleteAfterArchive`; do not parse raw YAML inside the skill.

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
   If delta specs or `opsx-delta.yaml` exist, assess whether sync is required. The archive CLI performs verify, sync, and move-to-archive; do not duplicate sync writes manually.

6. **Run archive CLI**
   Run `openspec archive "<change-name>"` after the verify gate is fresh. CLI only verifies, syncs, moves the change to archive, and prints the git handoff reminder. CLI MUST NOT create commits, merge branches, switch branches, delete branches, remove worktrees, or generate commit messages.

7. **Git handoff**
   Read the archive CLI output and the projected git policy from `openspec config project --json`. Summary fields include change name, schema, archive location, verify gate result, specs / OPSX sync result, agent-owned git follow-up status, and merge strategy.

8. **Agent git flow**
   The agent continues the post-archive git flow. First handle the implementation boundary before OpenSpec/docs archive artifacts. If uncommitted real project implementation changes remain, create a normal implementation commit that contains only those changes. Then always create a semantic boundary commit with `git commit --allow-empty`; this boundary commit may be intentionally empty when the effective implementation diff is already carried by retained `wip: opt-*` checkpoint commits. If `git.commitMessage.boundary` is set, read that project-relative path; otherwise read `openspec/references/openspec-boundary-commit-message.md`. Use that template to build the boundary commit message and run `git commit -F -` for the boundary commit. If `git.commitMessage.archive` is set, read that project-relative path; otherwise read `openspec/references/openspec-archive-commit-message.md`. Use that template before creating the OpenSpec/docs archive commit, add only archive/synced paths, and run `git commit -F -`. If a merge or squash commit message is needed, prepare it from the configured or built-in merge template. If `git.commitMessage.merge` is set, read that project-relative path; otherwise read `openspec/references/openspec-merge-summary-message.md`. Apply `git.merge.strategy` with `git merge --no-ff`, `git merge --ff-only`, or `git merge --squash` as appropriate. Use `git.branch.deleteAfterArchive` only after confirming the branch is merged with `git branch --merged`. Build paths with `path.join()`, `path.resolve()`, and `path.normalize()`.

9. **Display summary**
   Include change, schema, archive location, verify gate result, specs / OPSX sync result, agent-owned git follow-up status, Merge Strategy, cleanup responsibility, verify reuse/reexecution, and warnings. Do not report that CLI created an archive commit, performed a merge, or deleted a feature branch.

**Output On Success**

```
## Archive Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Archived to:** openspec/changes/archive/YYYY-MM-DD-<name>/
**Verify Gate:** Fresh PASS or PASS_WITH_WARNINGS result confirmed
**Specs / OPSX:** ✓ Synced to main specs and project OPSX (or "No deltas" or "Skipped all archive-time sync writes")
**Agent Git Follow-up:** <completed / pending with reason>
**Merge Strategy:** <git.merge.strategy>
**Cleanup Responsibility:** <agent>

Archive completed after satisfying the unified full verify gate.
```

**Guardrails**
- Always prompt for change selection if not provided
- Do not downgrade the verify gate into a lightweight archive-only check
- Show clearly whether verify was reused or re-executed
- In `core`, use `openspec sync "<change-name>"` rather than manual inline sync
- If delta specs or `opsx-delta.yaml` exist, always run the shared sync assessment before moving the change directory
