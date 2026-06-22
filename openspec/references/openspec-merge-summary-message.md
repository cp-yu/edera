# Merge Summary Message Template

Use this built-in format when `git.commitMessage.merge` is not configured.

Subject:

```text
<type>(<scope>): <English subject>
```

Body:

```text
## Why
[Business context] <why from proposal.md>
[Technical decision] <decision from design.md when present>

## Changes
- `<file-path>`: <why this file changed>
```

Rules:
- Build the summary from the archived `proposal.md`, `design.md`, `tasks.md`, and `opsx-delta.yaml`.
- Use `git commit -F -` for no-ff merge commits and squash commits that require a message.
- Do not generate this message for `ff-only` merges.