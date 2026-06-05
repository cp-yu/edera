export interface DagEdge {
  from: string
  to: string
  fan_out?: boolean
  fan_in?: boolean
  optional?: boolean
  fan_in_mode?: 'barrier' | 'accumulate' | 'collect' | 'stream'
  sourceHandle?: string
  targetHandle?: string
}

export interface DagInputDefinition {
  name: string
  type: string
  required?: boolean
  default?: unknown
}

export type NodeRole = 'source' | 'processor' | 'sink'

export interface InspectorSchemaProperty {
  type?: string
  enum?: string[]
  items?: InspectorSchemaProperty
  properties?: Record<string, InspectorSchemaProperty>
  default?: unknown
}

export interface InspectorSchema {
  type?: string
  properties?: Record<string, InspectorSchemaProperty>
}

export interface NodeType {
  name: string
  type: 'function' | 'agent' | 'dag' | 'wait'
  role: NodeRole
  input_type: string
  output_type: string
  skills: string[]
  handler?: string | null
  system_prompt_file?: string | null
  system_prompt?: string | null
  model?: string
  timeout_seconds?: number
  source_names?: string[]
  entities?: string[]
  entity_permissions?: Record<string, Record<string, string>>
  parameters?: Record<string, unknown>
  parameters_schema?: Record<string, unknown>
  emits?: EmitDeclaration[]
  inspector_schema: InspectorSchema
}

export interface NodeInstance extends NodeType {
  id: string
  type_name: string
  dag_ref?: string | null
  input_mapping?: Record<string, string>
  alias?: string | null
  config?: Record<string, unknown>
  optional?: boolean
}

export interface EntityTypeDefinition {
  display_name: string
  business_id_field: string
  display_template: string
  system_protected: boolean
  schema: Record<string, unknown>
  field_permissions: Record<string, string>
  validate: boolean
}

export interface EntityItem {
  id: string
  ref: string
  type: string
  display: string
  attributes: Record<string, unknown>
}

export interface EmitDeclaration {
  event: string
  condition?: string | null
}

export interface TriggerAttributes {
  name: string
  wait_for: string
  target: string
  enabled?: boolean
}

export interface EntityRelation {
  entities: string[]
  type: string
  metadata: Record<string, unknown>
}

export interface DagNodeRecord {
  id: string
  type: string
  dag_ref?: string | null
  input_mapping?: Record<string, string>
  alias?: string | null
  config?: Record<string, unknown>
  optional?: boolean
}

export interface DagUi {
  nodes?: Record<string, { x: number; y: number }>
  edges?: Record<string, { sourceHandle?: string; targetHandle?: string }>
}

export interface DagState {
  name: string
  inputs: DagInputDefinition[]
  nodes: NodeInstance[]
  edges: DagEdge[]
  ui: DagUi
  entity_types?: Record<string, EntityTypeDefinition>
  entities?: EntityItem[]
  entity_relations?: EntityRelation[]
}

export interface SkillDefinition {
  name: string
  description: string
  handler: string
  parameters_schema: Record<string, unknown>
}

export interface DagRun {
  id: number
  run_id: string
  dag_name: string
  source: string
  status: string
  started_at: string
  ended_at: string | null
  error: string | null
  retry_of?: string | null
}

export interface DagStatus {
  scheduler_running: boolean
  scheduler_paused: boolean
  dag_name: string
  current_run_id: string | null
  recent_runs: DagRun[]
}

export interface RetryDagResponse {
  run_id: string
  retry_of: string
  node_ids: string[]
  mode: 'single' | 'cascade'
  retry_nodes: string[]
}

export interface NodeStatus {
  status: string
  error: string | null
  run_id: string
  started_at?: string | null
  ended_at?: string | null
  metadata?: Record<string, unknown>
}

export interface NodeControlStatus {
  node_id: string
  status: string
}

export interface NodeResumeResponse {
  run_id: string
}

export interface RuntimeStatus {
  node_statuses: Record<string, NodeStatus>
}

export interface NodeOutputEntity {
  id: string
  type: string
  attributes: Record<string, unknown>
}

export interface NodeExecutionLog {
  id: number
  run_id: string
  node_id: string
  kind: string
  path: string
  digest: string
  size: number
  created_at: string
  updated_at: string
}

export interface NodeHistoryItem {
  run: DagRun
  node_run: {
    id: number
    run_id: string
    node_name: string
    status: string
    started_at: string | null
    ended_at: string | null
    error: string | null
  }
  outputs: NodeOutputEntity[]
  logs: NodeExecutionLog[]
}

export interface Briefing {
  id: string
  run_id: string
  content: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface Advice {
  id: string
  stock_code: string
  stock_name: string
  direction: string
  confidence: number
  reason: string
  evidence: number[]
  source_quotes: string[]
  source_urls: string[]
  portfolio_snapshot: Record<string, unknown>
  low_confidence: boolean
  created_at: string
  data_window_start: string
  data_window_end: string
  comparison: PriceComparison
}

export interface PriceComparison {
  verdict: string
  verdict_label?: string
  price_change_percent?: number
}

export interface EventRecord {
  id: string | number
  stock_code: string
  title: string
  status: string
  heat_score: number
  contradiction: boolean
  source_names: string[]
  evidence_count: number
  source_count: number
  first_seen_at: string
  last_seen_at: string
}

export interface ExtensionSummary {
  name: string
  version: string
  description?: string | null
  depends?: string[]
  enabled?: boolean
  installed_by?: string | null
  created_at?: string
}

export interface ExtensionDetail {
  manifest: {
    name: string
    version: string
    description?: string | null
    depends?: string[]
    handlers?: { name: string; entry?: string }[]
    entity_types?: { name: string; display_name?: string }[]
    imports?: { entities?: string[] }
  }
  import_records?: { import_path?: string; status?: string; entity_ref?: string }[]
}

export interface ResultsSummary {
  briefing: Briefing | null
  metadata_bar: Record<string, unknown>
  briefings: Briefing[]
  advices: Advice[]
  events: EventRecord[]
  event_details: Record<number, unknown>
  summary_items: Advice[]
  failed_sources: Record<string, string>
}

export interface SourceHealth {
  source_name: string
  latest_status: string
  run_id: string | null
  latest_run_at: string | null
  success_rate: number | null
  window_size: number
  recovery_status: string
  attempt_count: number
  recoverable_reason: string | null
  latest_failure_reason: string | null
  escalated: boolean
  escalation_reason: string | null
  repair_task: Record<string, unknown> | null
}

export interface SourceLog {
  run_id: string
  source_name: string
  status: string
  dag_status: string | null
  started_at: string | null
  ended_at: string | null
  error: string | null
}
