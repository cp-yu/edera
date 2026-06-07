## Apply Phase 2 Optimization Protocol

The checkpoint is a git stash entry, not a git tag. Do not create tag checkpoints for apply optimization.

1. Skip Phase 2 only when the user requested `--skip-optimization` or `optimization.enabled: false`; record `SKIPPED` through `openspec verify phase2`.
2. Read `optimization.optRetries` from `openspec/config.yaml`; default to `2`.
3. Before the first optimization attempt, save the Phase 1 baseline:
   ```bash
   git stash push -u -m "apply-opt-checkpoint-r0"
   ```
4. Spawn the optimizer subagent and instruct it to invoke the `openspec-optimizer` skill. The optimizer proposes Search/Replace blocks only; it MUST NOT edit files.
5. For each proposed optimization, record pre-patch hashes before editing:
   ```bash
   openspec verify phase2 "<change-name>" --type=optimization --files "<affected-files>" --input '<json>' --json
   ```
6. Apply Search/Replace blocks atomically, then spawn the reviewer subagent for speculative Phase 1 re-verification.
7. On speculative PASS, record verification PASS. If another retry remains, save the new successful state:
   ```bash
   git stash push -u -m "apply-opt-checkpoint-r<N>"
   ```
8. On speculative FAIL, restore the latest checkpoint:
   ```bash
   git reset --hard HEAD
   git clean -fd
   git stash apply stash@{0}
   ```
   Record the failed direction in `.verify-result.json`; the checkpoint is not consumed.
9. Each complete proposal + patch + reviewer re-verify loop consumes one `optRetries` budget, whether it passes or fails. Format or Search/Replace matching problems are handled by the main agent and do not consume retry budget.
10. When all attempts finish, consume all `apply-opt-checkpoint-*` stash entries only after the final safe workspace state is confirmed.