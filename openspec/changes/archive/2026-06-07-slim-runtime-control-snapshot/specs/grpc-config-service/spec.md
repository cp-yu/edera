## ADDED Requirements

### Requirement: ConfigService reload RPC removal
`ConfigService` SHALL NOT expose `ReloadEntityTypes` or `ReloadSkills` RPCs. EntityType and Skill configuration SHALL use DB-backed source of truth and MUST NOT require runtime snapshot reload APIs.

#### Scenario: EntityType reload RPC absent
- **WHEN** clients inspect the ConfigService API
- **THEN** `ReloadEntityTypes` MUST NOT be available

#### Scenario: Skill reload RPC absent
- **WHEN** clients inspect the ConfigService API
- **THEN** `ReloadSkills` MUST NOT be available

#### Scenario: EntityType save does not mutate runtime control snapshot
- **WHEN** EntityType metadata is saved to DB
- **THEN** system SHALL emit `event:config-changed`
- **AND** system MUST NOT mutate `RuntimeControlSnapshot` in place

#### Scenario: Skill save does not mutate runtime control snapshot
- **WHEN** Skill metadata is saved to DB
- **THEN** system SHALL emit `event:config-changed`
- **AND** system MUST NOT mutate `RuntimeControlSnapshot` in place
