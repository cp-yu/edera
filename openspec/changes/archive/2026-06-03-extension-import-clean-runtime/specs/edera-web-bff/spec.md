## ADDED Requirements

### Requirement: No hard-coded default DAG routes
`edera-web` SHALL expose DAG run, stop, status and history behavior through parameterized DAG routes. It MUST NOT provide hard-coded `default` DAG compatibility routes that bypass the `{dag_name}` path parameter.

#### Scenario: Run default through parameterized route
- **WHEN** client needs to run DAG `default`
- **THEN** client SHALL call `POST /api/dags/default/run`
- **AND** the route SHALL be handled by the generic `/api/dags/{dag_name}/run` handler

#### Scenario: No duplicate default run route
- **WHEN** web routes are registered
- **THEN** there MUST NOT be a separate route handler dedicated to `/api/dags/default/run`

#### Scenario: No default-only node history route
- **WHEN** client queries node history
- **THEN** client SHALL use a route that includes the DAG name
- **AND** web routes MUST NOT hard-code `dag_name = "default"` for history queries
