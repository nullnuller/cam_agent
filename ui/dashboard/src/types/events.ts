export type ViolationSeverity = 'info' | 'warn' | 'block'

export interface ViolationDetail extends Record<string, unknown> {
  category: string
  severity: ViolationSeverity
  violation_type?: string | null
  clause_reference?: string | null
  description?: string | null
}

export interface EventSource extends Record<string, unknown> {
  model_id: string
  provider: string
  mode?: string | null
  metadata?: Record<string, unknown>
}

export interface RunMetadata {
  run_id: string
  scenario_id?: string | null
  started_at: string
  tags?: Record<string, string>
}

export type TimelineEventType =
  | 'user_prompt'
  | 'llm_response'
  | 'judge_verdict'
  | 'metric_snapshot'
  | 'audit_record'

export interface TimelineEvent<TPayload extends Record<string, unknown> = Record<string, unknown>> {
  run: RunMetadata
  exchange_id: string
  turn_index: number
  event_type: TimelineEventType
  payload: TPayload
  created_at: string
}

export interface UserPromptPayload extends Record<string, unknown> {
  source: EventSource
  prompt_text: string
  prompt_redacted?: string | null
  question_category?: string | null
}

export interface LLMResponsePayload extends Record<string, unknown> {
  source: EventSource
  question_category?: string
  prompt_preview?: string
  completion_preview?: string
  latency_ms?: number
  token_usage?: Record<string, number>
  context_tokens?: number
  pii_redacted_text?: string
  pii_raw_text?: string
  pii_fields?: string[]
}

export interface JudgeVerdictPayload extends Record<string, unknown> {
  source: EventSource
  verdict: 'allow' | 'warn' | 'block'
  score?: number
  rationale_redacted?: string
  rationale_raw?: string
  violation?: ViolationDetail
  latency_ms?: number
}
