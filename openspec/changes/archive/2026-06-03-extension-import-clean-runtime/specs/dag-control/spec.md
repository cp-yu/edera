## ADDED Requirements

### Requirement: Startup does not run DAG
`DagController.start()` SHALL initialize runtime dependencies, runtime snapshot, scheduler state and cron loop without starting any DAG run.

#### Scenario: Controller start is idle
- **WHEN** `DagController.start()` completes
- **THEN** no `DagRun` record SHALL be created by startup
- **AND** no DAG SHALL appear in `active_runs` solely because the controller started

### Requirement: Manual DAG run uses emit path
系统 SHALL route manual DAG run requests through `TriggerExecutor.emit("manual:dag:<name>")`. The manual emit MUST directly fire the DAG target, preserve payload, and create a `DagRun` whose `source` is `manual`.

#### Scenario: DagService run emits manual event
- **WHEN** `DagService.Run` receives `DagRunRequest{name: "default", inputs_json: "{\"symbol\":\"TEST\"}"}`
- **THEN** server SHALL call controller emit path for `manual:dag:default`
- **AND** the DAG run SHALL receive payload `{"symbol": "TEST"}`

#### Scenario: Manual emit does not set event bit
- **WHEN** `emit("manual:dag:default")` is called
- **THEN** system SHALL fire `dag:default`
- **AND** MUST NOT persist `manual:dag:default` as an EventGroup bit
