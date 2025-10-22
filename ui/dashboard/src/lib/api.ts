import type {
  RunMetadata,
  TimelineEvent,
  LLMResponsePayload,
  JudgeVerdictPayload,
  EventSource as TimelineEventSource,
  ViolationDetail,
} from '../types/events'

export type RevealField = 'llm_response' | 'judge_rationale'

export interface ConsoleScenarioOption {
  id: string
  label: string
  model: string
  use_rag: boolean
}

export interface ConsoleJudgeOption {
  id: string
  label: string
  available: boolean
  description?: string
}

export interface ConsoleOptions {
  scenarios: ConsoleScenarioOption[]
  judges: ConsoleJudgeOption[]
}

export interface ConsoleSubmitParams {
  prompt: string
  scenarioId: string
  judgeId: string
}

export interface ConsoleSubmitResult {
  status: string
  run: RunMetadata
  events: Array<TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>>
}

const API_BASE =
  import.meta.env.VITE_CAM_API_BASE?.replace(/\/$/, '') ?? 'http://localhost:8000'

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Request failed (${response.status}): ${detail}`)
  }
  return (await response.json()) as T
}

function ensureSource(raw: any): TimelineEventSource {
  if (raw && typeof raw === 'object' && 'model_id' in raw) {
    return {
      model_id: String(raw.model_id ?? 'unknown-model'),
      provider: String(raw.provider ?? 'pipeline'),
      mode: raw.mode ? String(raw.mode) : null,
      metadata: (raw.metadata as Record<string, unknown>) ?? {},
    }
  }
  return {
    model_id: 'unknown-model',
    provider: 'pipeline',
    mode: null,
    metadata: {},
  }
}

function ensureViolation(raw: any): ViolationDetail | undefined {
  if (!raw || typeof raw !== 'object') return undefined
  return {
    category: String(raw.category ?? 'policy_violation'),
    severity: (raw.severity as 'info' | 'warn' | 'block') ?? 'warn',
    violation_type: raw.violation_type ? String(raw.violation_type) : null,
    clause_reference: raw.clause_reference ? String(raw.clause_reference) : null,
    description: raw.description ? String(raw.description) : null,
  }
}

function ensureStringArray(raw: any): string[] | undefined {
  if (!Array.isArray(raw)) return undefined
  return raw.map((value) => String(value))
}

function toTimelineEvent(
  raw: any,
): TimelineEvent<LLMResponsePayload | JudgeVerdictPayload> {
  const createdAt = String(raw.created_at ?? new Date().toISOString())
  const base: TimelineEvent<LLMResponsePayload | JudgeVerdictPayload> = {
    run: {
      run_id: String(raw.run?.run_id ?? 'unknown-run'),
      scenario_id: raw.run?.scenario_id ?? null,
      started_at: String(raw.run?.started_at ?? createdAt),
      tags: (raw.run?.tags as Record<string, string>) ?? {},
    },
    exchange_id: String(raw.exchange_id ?? 'exchange-unknown'),
    turn_index: Number(raw.turn_index ?? 0),
    event_type: String(raw.event_type ?? 'audit_record') as TimelineEvent['event_type'],
    payload: {} as LLMResponsePayload | JudgeVerdictPayload,
    created_at: createdAt,
  }

  if (base.event_type === 'judge_verdict') {
    const payload = raw.payload ?? {}
    base.payload = {
      source: ensureSource(payload.source),
      verdict: String(payload.verdict ?? 'allow') as JudgeVerdictPayload['verdict'],
      score: payload.score ?? undefined,
      rationale_redacted: payload.rationale_redacted ?? payload.rationale_raw ?? undefined,
      rationale_raw: payload.rationale_raw ?? undefined,
      violation: ensureViolation(payload.violation),
      latency_ms: payload.latency_ms ?? undefined,
    }
  } else {
    const payload = raw.payload ?? {}
    base.event_type = 'llm_response'
    base.payload = {
      source: ensureSource(payload.source),
      question_category: payload.question_category ?? null,
      prompt_preview: payload.prompt_preview ?? undefined,
      completion_preview: payload.completion_preview ?? undefined,
      latency_ms: payload.latency_ms ?? undefined,
      token_usage: (payload.token_usage as Record<string, number>) ?? {},
      context_tokens: payload.context_tokens ?? undefined,
      pii_redacted_text:
        payload.pii_redacted_text ??
        payload.pii_raw_text ??
        payload.final_text ??
        '',
      pii_raw_text: payload.pii_raw_text ?? undefined,
      pii_fields: ensureStringArray(payload.pii_fields),
    }
  }

  return base
}

export async function fetchRuns(): Promise<RunMetadata[]> {
  const runs = await request<RunMetadata[]>('/runs')
  return runs
    .map((run) => ({
      run_id: String(run.run_id),
      scenario_id: run.scenario_id ?? null,
      started_at: run.started_at,
      tags: run.tags ?? {},
    }))
    .sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
}

export async function fetchConsoleOptions(): Promise<ConsoleOptions> {
  return request<ConsoleOptions>('/console/options')
}

export async function fetchTimeline(
  runId: string,
): Promise<TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>[]> {
  const events = await request<any[]>(`/runs/${encodeURIComponent(runId)}/timeline`)
  return events.map(toTimelineEvent)
}

export async function submitPrompt(params: ConsoleSubmitParams): Promise<ConsoleSubmitResult> {
  const response = await fetch(`${API_BASE}/console`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt: params.prompt,
      scenario_id: params.scenarioId,
      judge_id: params.judgeId,
    }),
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Console request failed (${response.status}): ${detail}`)
  }
  const payload = (await response.json()) as ConsoleSubmitResult
  return {
    status: payload.status,
    run: {
      run_id: String(payload.run.run_id),
      scenario_id: payload.run.scenario_id ?? null,
      started_at: payload.run.started_at,
      tags: payload.run.tags ?? {},
    },
    events: payload.events.map(toTimelineEvent),
  }
}

export interface TimelineStreamOptions {
  replay?: boolean
  pollInterval?: number
  onEvent: (event: TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>) => void
  onOpen?: () => void
  onError?: (event: Event) => void
  onHeartbeat?: () => void
}

export interface TimelineStreamSubscription {
  source: EventSource
  close: () => void
}

export function subscribeTimelineStream(
  runId: string,
  {
    replay = true,
    pollInterval,
    onEvent,
    onOpen,
    onError,
    onHeartbeat,
  }: TimelineStreamOptions,
): TimelineStreamSubscription {
  const params = new URLSearchParams()
  params.set('run_id', runId)
  params.set('replay', replay ? 'true' : 'false')
  if (pollInterval) {
    params.set('poll_interval', String(pollInterval))
  }

  const source = new EventSource(`${API_BASE}/stream?${params.toString()}`)
  const listener = (event: MessageEvent<string>) => {
    try {
      const raw = JSON.parse(event.data)
      onEvent(toTimelineEvent(raw))
    } catch (error) {
      console.error('Failed to parse timeline stream event', error)
    }
  }

  const llmListener = listener as EventListener
  source.addEventListener('llm_response', llmListener)
  source.addEventListener('judge_verdict', llmListener)

  const heartbeatListener = ((_: Event) => {
    if (onHeartbeat) {
      onHeartbeat()
    }
  }) as EventListener
  if (onHeartbeat) {
    source.addEventListener('heartbeat', heartbeatListener)
  }

  if (onOpen) {
    source.onopen = onOpen
  }

  source.onerror = (event) => {
    if (onError) {
      onError(event)
    } else {
      console.warn('Timeline stream error', event)
    }
  }

  const close = () => {
    source.removeEventListener('llm_response', llmListener)
    source.removeEventListener('judge_verdict', llmListener)
    if (onHeartbeat) {
      source.removeEventListener('heartbeat', heartbeatListener)
    }
    source.close()
  }

  return { source, close }
}

export async function recordReveal(params: {
  runId: string
  exchangeId: string
  field: RevealField
  reason?: string
}): Promise<void> {
  const response = await fetch(`${API_BASE}/reveal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      run_id: params.runId,
      exchange_id: params.exchangeId,
      field: params.field,
      reason: params.reason,
    }),
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText)
    throw new Error(`Reveal logging failed (${response.status}): ${detail}`)
  }
}
