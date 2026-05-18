export interface DagEdge {
  from: string
  to: string
  fan_out?: boolean
  fan_in?: boolean
  sourceHandle?: string
  targetHandle?: string
}

export type NodeRole = 'source' | 'processor' | 'sink'

export interface NodeType {
  name: string
  type: 'function' | 'llm'
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
  parameters?: Record<string, unknown>
}

export interface NodeInstance extends NodeType {
  id: string
  type_name: string
  alias?: string | null
  config?: Record<string, unknown>
}

export interface DagNodeRecord {
  id: string
  type: string
  alias?: string | null
  config?: Record<string, unknown>
}

export interface DagUi {
  nodes?: Record<string, { x: number; y: number }>
  edges?: Record<string, { sourceHandle?: string; targetHandle?: string }>
}

export interface DagState {
  name: string
  nodes: NodeInstance[]
  edges: DagEdge[]
  ui: DagUi
}

export interface SkillDefinition {
  name: string
  description: string
  handler: string
  parameters_schema: Record<string, unknown>
}

export interface PipelineRun {
  id: number
  cycle_id: string
  dag_name: string
  trigger: string
  status: string
  started_at: string
  ended_at: string | null
  error: string | null
}

export interface DagStatus {
  scheduler_running: boolean
  scheduler_paused: boolean
  dag_name: string
  current_cycle_id: string | null
  recent_runs: PipelineRun[]
}

export interface NodeStatus {
  status: string
  error: string | null
  cycle_id: string
}

export interface RuntimeStatus {
  node_statuses: Record<string, NodeStatus>
}

export interface Briefing {
  id: number
  cycle_id: string
  content: string
  metadata_: Record<string, unknown>
  created_at: string
}

export interface Advice {
  id: number
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
  id: number
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
  cycle_id: string | null
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
  cycle_id: string
  source_name: string
  node_status: string
  pipeline_status: string
  started_at: string | null
  ended_at: string | null
  error: string | null
}
