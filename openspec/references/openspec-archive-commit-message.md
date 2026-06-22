# Archive Commit Message Template

Use this built-in format when `git.commitMessage.archive` is not configured.

Subject:

```text
docs(<change-name>): Archive change artifacts
```

Body:

```text
## Why
[Business context] <why this archive commit is needed>

## Changes
- `<file-path>`: <why this archived/synced path must be committed>
```

Rules:
- Include only archive/synced paths selected for the archive commit.
- Keep non-archive dirty changes out of the commit.
- Pass the message through `git commit -F -`.