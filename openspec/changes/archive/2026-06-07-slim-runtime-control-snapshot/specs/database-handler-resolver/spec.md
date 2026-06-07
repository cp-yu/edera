## ADDED Requirements

### Requirement: Run-start resolver snapshot
`DatabaseHandlerResolver` SHALL support creating a run-start snapshot that freezes enabled extension handler metadata for one `DagExecutionSnapshot`.

#### Scenario: Snapshot freezes handlers
- **WHEN** `DatabaseHandlerResolver.snapshot(session)` is called at DAG run start
- **THEN** returned resolver SHALL contain the enabled handlers visible in DB at that time

#### Scenario: Later extension changes do not affect resolver snapshot
- **WHEN** an extension is installed or disabled after resolver snapshot creation
- **THEN** the existing resolver snapshot SHALL continue resolving only its frozen handler set

### Requirement: Extension table mapping freezes with resolver
System SHALL freeze extension storage table mappings in the same `DagExecutionSnapshot` that freezes `DatabaseHandlerResolver`.

#### Scenario: Handler storage table mapping is consistent
- **WHEN** a handler resolved by the snapshot calls `ctx.storage.table("items")`
- **THEN** system SHALL resolve the table name from the `extension_table_names` frozen for the same `DagExecutionSnapshot`
