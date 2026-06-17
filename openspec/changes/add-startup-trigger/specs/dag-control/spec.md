## ADDED Requirements

### Requirement: Startup window auto-runs declared startup triggers
`DagController.start()` SHALL open a startup window after runtime initialization (bootstrap, snapshot install, scheduler start, cron loop creation) completes. During the window the system SHALL treat the `startup` token as a set broadcast bit in `EventGroup`, and SHALL fire every Trigger whose `wait_for` expression evaluates true under the active event set, creating one `DagRun` per fire with `source = "startup"`.

The startup window length SHALL be configurable via `system.toml` field `startup_window_seconds` (default `10`). When the window expires the system SHALL clear the `startup` bit; subsequent `startup` evaluations SHALL be false.

The `startup` bit SHALL NOT participate in `EventGroup.consume()` semantics: a fire event SHALL NOT remove `startup` from the active set. Only window expiry or explicit `clear("startup")` SHALL remove it.

On every `DagController.start()` invocation, before opening the window, the system SHALL `clear("startup")` to defend against bit residue from a prior crashed process.

#### Scenario: Startup fires single declared startup trigger
- **WHEN** `DagController.start()` completes with one Trigger Entity `wait_for: 'startup'`, `target: 'dag:bootstrap'`, `enabled: true`
- **THEN** the system SHALL create exactly one `DagRun` for `dag:bootstrap` with `source = "startup"`
- **AND** the `startup` bit SHALL remain set in `EventGroup` until the window expires

#### Scenario: Startup fires multiple declared startup triggers concurrently
- **WHEN** `DagController.start()` completes with three Trigger Entities all `wait_for: 'startup'` targeting different DAGs
- **THEN** the system SHALL create one `DagRun` per trigger, all with `source = "startup"`
- **AND** the first fire SHALL NOT consume the `startup` bit, so all three triggers SHALL evaluate true

#### Scenario: Startup window expires and clears bit
- **WHEN** `startup_window_seconds` is `10` (default) and 10 seconds have elapsed since `DagController.start()` completed
- **THEN** the system SHALL clear the `startup` bit from `EventGroup`
- **AND** subsequent evaluations of any `wait_for` expression containing `startup` SHALL be false

#### Scenario: Startup window length is configurable
- **WHEN** `system.toml` sets `startup_window_seconds = 1` and `DagController.start()` completes
- **THEN** the system SHALL clear the `startup` bit 1 second after start
- **AND** the default value `10` SHALL apply when the field is absent

#### Scenario: Crashed-process residue is cleared before opening window
- **WHEN** `event_group_bits` contains a residue row for `startup` from a prior crashed process, and `DagController.start()` is invoked
- **THEN** the system SHALL clear the residue `startup` bit before setting a fresh one
- **AND** only one `startup` row SHALL exist in `event_group_bits` during the new window

#### Scenario: Shutdown cancels in-flight startup-triggered runs without replay
- **WHEN** a startup-triggered `DagRun` is still executing and `DagController.shutdown()` is invoked
- **THEN** the system SHALL cancel the running task and mark the `DagRun` as `cancelled`
- **AND** the next `DagController.start()` SHALL open a fresh startup window rather than resuming the cancelled run

#### Scenario: Startup trigger fires with compound expression within window
- **WHEN** a Trigger Entity has `wait_for: 'startup AND event:market-open'`, `event:market-open` is set within the startup window, and `DagController.start()` has completed
- **THEN** the system SHALL fire the trigger exactly once
- **AND** the resulting `DagRun.source` SHALL be `"startup"`

## MODIFIED Requirements

### Requirement: Startup does not run DAG
`DagController.start()` SHALL initialize runtime dependencies, `RuntimeControlSnapshot`, scheduler state and cron loop without starting any DAG run solely because the controller started. The startup window defined in `Startup window auto-runs declared startup triggers` is the only startup-side path that creates `DagRun` records, and it SHALL only fire Triggers whose `wait_for` expression explicitly references the `startup` token. The system MUST NOT load all DAG/Node configs solely because the controller started.

#### Scenario: Controller start is idle for non-startup DAGs
- **WHEN** `DagController.start()` completes and no Trigger Entity declares `wait_for` containing the `startup` token
- **THEN** no `DagRun` record SHALL be created by startup
- **AND** no DAG SHALL appear in `active_runs` solely because the controller started
- **AND** system MUST NOT load all DAG/Node configs solely because the controller started

#### Scenario: Controller start fires only declared startup triggers
- **WHEN** `DagController.start()` completes and one or more Trigger Entities declare `wait_for` referencing `startup`
- **THEN** the system SHALL create `DagRun` records only for those declared triggers
- **AND** every such `DagRun.source` SHALL be `"startup"`
- **AND** DAGs without a matching startup Trigger SHALL NOT be auto-run
