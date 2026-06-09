# Archive Commit Message Convention

Use this format when `git.archive.commitMessage.convention` is `openspec-archive`.

```yaml
convention: openspec-archive
```

Subject:

```text
docs(<change-name>): 归档变更制品
```

Body:

```text
## Why
[业务背景] <why this archive commit is needed>

## Changes
- `<file-path>`: <why this archived/synced path must be committed>
```

Rules:
- Include only archive/synced paths selected for the archive commit.
- Keep non-archive dirty changes out of the commit.
- Pass the message through `git commit -F -`.