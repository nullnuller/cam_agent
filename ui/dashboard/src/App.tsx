import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Timeline } from './features/timeline/Timeline'
import { PlaybackControls } from './features/timeline/PlaybackControls'
import { MetricsPanel } from './features/metrics/MetricsPanel'
import { SafetyPanel } from './features/safety/SafetyPanel'
import { LiveConsole } from './features/console/LiveConsole'
import { RunSelector } from './features/run/RunSelector'
import { FilterPanel } from './features/filters/FilterPanel'
import {
  fetchRuns,
  fetchTimeline,
  submitPrompt,
  fetchConsoleOptions,
  subscribeTimelineStream,
  recordReveal,
  type ConsoleSubmitParams,
  type TimelineStreamSubscription,
} from './lib/api'
import type {
  TimelineEvent,
  LLMResponsePayload,
  JudgeVerdictPayload,
  ViolationDetail,
  RunMetadata,
} from './types/events'
import './index.css'

type ViolationSummary = ViolationDetail & { count: number }

const demoRun: RunMetadata = {
  run_id: 'demo-session',
  scenario_id: 'A',
  started_at: new Date().toISOString(),
  tags: {},
}

const demoEvents: TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>[] = [
  {
    run: demoRun,
    exchange_id: 'ex-1',
    turn_index: 0,
    event_type: 'llm_response',
    created_at: new Date().toISOString(),
    payload: {
      source: {
        model_id: 'gemma3-4B-128k',
        provider: 'llama.cpp',
        mode: 'rag',
        metadata: {},
      },
      pii_redacted_text:
        'The APP6.1(a) clause allows a maintenance release for minor defects when a licensed engineer confirms continued airworthiness.',
      latency_ms: 1850,
      token_usage: { prompt: 1024, completion: 512 },
      question_category: 'regulatory_lookup',
    },
  },
  {
    run: demoRun,
    exchange_id: 'ex-1',
    turn_index: 0,
    event_type: 'judge_verdict',
    created_at: new Date().toISOString(),
    payload: {
      source: {
        model_id: 'google_medgemma-27b',
        provider: 'ollama',
        mode: 'judge',
        metadata: {},
      },
      verdict: 'warn',
      rationale_redacted:
        'Response missing explicit disclaimer and lacks citations for APP references.',
      violation: {
        category: 'disclaimer_missing',
        severity: 'warn',
        violation_type: 'compliance',
        description: 'Add healthcare disclaimer reminding users to validate with professionals.',
      },
      latency_ms: 7200,
    },
  },
]

function formatLatency(msTotal: number | undefined, count: number): string {
  if (!msTotal || count === 0) return '—'
  const avg = msTotal / count
  if (avg >= 1000) {
    return `${(avg / 1000).toFixed(2)}s`
  }
  return `${Math.round(avg)}ms`
}

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackIndex, setPlaybackIndex] = useState(-1)
  const [playbackSpeed, setPlaybackSpeed] = useState(1)
  const [showAllTurns, setShowAllTurns] = useState(false)
  const [selectedQuestionCategories, setSelectedQuestionCategories] = useState<Set<string>>(
    () => new Set(),
  )
  const [selectedViolationCategories, setSelectedViolationCategories] = useState<Set<string>>(
    () => new Set(),
  )
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [selectedScenarioOption, setSelectedScenarioOption] = useState<string | null>(null)
  const [selectedJudgeOption, setSelectedJudgeOption] = useState<string | null>('none')
  const queryClient = useQueryClient()
  const [streamEvents, setStreamEvents] = useState<
    TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>[]
  >([])
  const [streamStatus, setStreamStatus] = useState<'idle' | 'connected' | 'error'>('idle')
  const streamSubscription = useRef<TimelineStreamSubscription | null>(null)

  const runsQuery = useQuery({
    queryKey: ['runs'],
    queryFn: fetchRuns,
    staleTime: 30_000,
  })

  const consoleOptionsQuery = useQuery({
    queryKey: ['console-options'],
    queryFn: fetchConsoleOptions,
    staleTime: 60_000,
  })

  const timelineQuery = useQuery({
    queryKey: ['timeline', selectedRunId],
    queryFn: () => fetchTimeline(selectedRunId ?? ''),
    enabled: Boolean(selectedRunId),
    staleTime: 10_000,
  })

  const noRunsAvailable =
    !runsQuery.isLoading && (runsQuery.data?.length ?? 0) === 0

  const usingDemoData =
    (!timelineQuery.data && timelineQuery.isError) ||
    (noRunsAvailable && !selectedRunId)

  useEffect(() => {
    if (runsQuery.data?.length) {
      setSelectedRunId((current) => current ?? runsQuery.data![0].run_id)
    } else if (!runsQuery.isLoading) {
      setSelectedRunId(null)
    }
  }, [runsQuery.data, runsQuery.isLoading])

  useEffect(() => {
    const scenarios = consoleOptionsQuery.data?.scenarios ?? []
    if (scenarios.length && !selectedScenarioOption) {
      setSelectedScenarioOption(scenarios[0].id)
    } else if (
      scenarios.length &&
      selectedScenarioOption &&
      !scenarios.some((option) => option.id === selectedScenarioOption)
    ) {
      setSelectedScenarioOption(scenarios[0].id)
    }

    const judges = consoleOptionsQuery.data?.judges ?? []
    if (!judges.length) {
      return
    }
    const currentJudgeValid = selectedJudgeOption
      ? judges.some((option) => option.id === selectedJudgeOption && option.available)
      : false
    if (currentJudgeValid) {
      return
    }
    const fallback =
      judges.find((option) => option.id === 'none') ??
      judges.find((option) => option.available) ??
      judges[0]
    if (fallback) {
      setSelectedJudgeOption(fallback.id)
    }
  }, [consoleOptionsQuery.data, selectedScenarioOption, selectedJudgeOption])

  useEffect(() => {
    setFiltersOpen(false)
  }, [selectedRunId])

  useEffect(() => {
    if (!selectedRunId || usingDemoData) {
      if (streamSubscription.current) {
        streamSubscription.current.close()
        streamSubscription.current = null
      }
      setStreamEvents([])
      setStreamStatus('idle')
      return
    }

    if (streamSubscription.current) {
      streamSubscription.current.close()
      streamSubscription.current = null
    }

    setStreamStatus('idle')
    const subscription = subscribeTimelineStream(selectedRunId, {
      replay: false,
      onOpen: () => setStreamStatus('connected'),
      onEvent: (event) => {
        setStreamStatus((prev) => (prev === 'connected' ? prev : 'connected'))
        setStreamEvents((prev) => {
          const exists = prev.some(
            (existing) =>
              existing.exchange_id === event.exchange_id &&
              existing.event_type === event.event_type &&
              existing.created_at === event.created_at,
          )
          if (exists) {
            return prev
          }
          const next = [...prev, event]
          return next.length > 500 ? next.slice(-500) : next
        })
      },
      onError: () => setStreamStatus('error'),
      onHeartbeat: () =>
        setStreamStatus((prev) => (prev === 'connected' ? prev : 'connected')),
    })
    streamSubscription.current = subscription

    return () => {
      subscription.close()
      if (streamSubscription.current === subscription) {
        streamSubscription.current = null
      }
      setStreamEvents([])
      setStreamStatus('idle')
    }
  }, [selectedRunId, usingDemoData])

  useEffect(() => {
    if (timelineQuery.data && selectedRunId) {
      setStreamEvents([])
    }
  }, [timelineQuery.data, selectedRunId])

  const fetchedEvents =
    timelineQuery.data ?? (usingDemoData ? demoEvents : [])

  const combinedEvents = useMemo(
    () => {
      const seen = new Set<string>()
      const merged: TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>[] = []
      const push = (event: TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>) => {
        const key = `${event.event_type}|${event.exchange_id}|${event.created_at}`
        if (seen.has(key)) return
        seen.add(key)
        merged.push(event)
      }
      fetchedEvents.forEach(push)
      streamEvents.forEach(push)
      return merged
    },
    [fetchedEvents, streamEvents],
  )

  useEffect(() => {
    const defaultIndex = combinedEvents.length > 0 ? combinedEvents.length - 1 : -1
    setPlaybackIndex(defaultIndex)
    setIsPlaying(false)
    setShowAllTurns(false)
  }, [selectedRunId, combinedEvents.length])

  const orderedEvents = useMemo(
    () =>
      combinedEvents
        .slice()
        .sort(
          (a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        ),
    [combinedEvents],
  )

  const exchangeQuestionCategory = useMemo(() => {
    const map = new Map<string, string>()
    for (const event of orderedEvents) {
      if (event.event_type === 'llm_response') {
        const rawCategory = (event.payload as LLMResponsePayload).question_category
        const category = rawCategory && rawCategory.trim().length > 0 ? rawCategory : 'Uncategorized'
        map.set(event.exchange_id, category)
      }
    }
    return map
  }, [orderedEvents])

  const exchangeViolationCategories = useMemo(() => {
    const map = new Map<string, Set<string>>()
    for (const event of orderedEvents) {
      if (event.event_type === 'judge_verdict') {
        const payload = event.payload as JudgeVerdictPayload
        const category = payload.violation?.category?.trim() || 'policy_violation'
        if (!map.has(event.exchange_id)) {
          map.set(event.exchange_id, new Set())
        }
        map.get(event.exchange_id)!.add(category)
      }
    }
    return map
  }, [orderedEvents])

  const availableQuestionCategories = useMemo(() => {
    const unique = new Set<string>()
    exchangeQuestionCategory.forEach((value) => {
      if (value) unique.add(value)
    })
    return Array.from(unique).sort()
  }, [exchangeQuestionCategory])

  const availableViolationCategories = useMemo(() => {
    const unique = new Set<string>()
    exchangeViolationCategories.forEach((set) => {
      set.forEach((value) => unique.add(value))
    })
    return Array.from(unique).sort()
  }, [exchangeViolationCategories])
  const activeFilterCount =
    selectedQuestionCategories.size + selectedViolationCategories.size

  const filteredEvents = useMemo(() => {
    const questionActive = selectedQuestionCategories.size > 0
    const violationActive = selectedViolationCategories.size > 0
    if (!questionActive && !violationActive) {
      return orderedEvents
    }
    return orderedEvents.filter((event) => {
      const exchangeId = event.exchange_id
      const questionCategory = exchangeQuestionCategory.get(exchangeId)
      const violationSet = exchangeViolationCategories.get(exchangeId)

      const questionMatches =
        !questionActive ||
        (questionCategory ? selectedQuestionCategories.has(questionCategory) : false)

      const violationMatches =
        !violationActive ||
        (violationSet
          ? Array.from(violationSet).some((category) => selectedViolationCategories.has(category))
          : false)

      return questionMatches && violationMatches
    })
  }, [
    orderedEvents,
    exchangeQuestionCategory,
    exchangeViolationCategories,
    selectedQuestionCategories,
    selectedViolationCategories,
  ])

  const activeEvents = useMemo(() => {
    if (filteredEvents.length === 0) {
      return [] as TimelineEvent<LLMResponsePayload | JudgeVerdictPayload>[]
    }
    const clampedIndex = Math.min(Math.max(playbackIndex, -1), filteredEvents.length - 1)
    if (clampedIndex < 0) {
      return []
    }
    return filteredEvents.slice(0, clampedIndex + 1)
  }, [filteredEvents, playbackIndex])

  const displayEvents = useMemo(() => {
    if (showAllTurns) {
      return activeEvents
    }
    return activeEvents.slice(-1)
  }, [activeEvents, showAllTurns])

  useEffect(() => {
    if (filteredEvents.length === 0) {
      setPlaybackIndex(-1)
      setIsPlaying(false)
      return
    }
    setPlaybackIndex((prev) => {
      if (prev < 0) {
        return filteredEvents.length - 1
      }
      return Math.min(prev, filteredEvents.length - 1)
    })
  }, [filteredEvents.length])

  useEffect(() => {
    if (!isPlaying) return
    if (filteredEvents.length === 0) {
      setIsPlaying(false)
      return
    }
    if (playbackIndex >= filteredEvents.length - 1) {
      setIsPlaying(false)
      return
    }
    const delay = Math.max(200, 1200 / playbackSpeed)
    const timer = window.setTimeout(() => {
      setPlaybackIndex((prev) => Math.min(prev + 1, filteredEvents.length - 1))
    }, delay)
    return () => window.clearTimeout(timer)
  }, [isPlaying, playbackIndex, filteredEvents.length, playbackSpeed])

  const safetyViolations = useMemo<ViolationSummary[]>(() => {
    const relevantEvents = (showAllTurns ? activeEvents : displayEvents).filter(
      (event) => event.event_type === 'judge_verdict',
    )
    const summaries = new Map<string, ViolationSummary>()
    relevantEvents.forEach((event) => {
      const payload = event.payload as JudgeVerdictPayload
      const violation = payload.violation
      if (!violation) return
      const key = [
        violation.category,
        violation.severity,
        violation.violation_type ?? '',
        violation.clause_reference ?? '',
        violation.description ?? '',
      ].join('|')
      const existing = summaries.get(key)
      if (existing) {
        summaries.set(key, { ...existing, count: existing.count + 1 })
      } else {
        summaries.set(key, {
          ...violation,
          count: 1,
        })
      }
    })
    const ordered = Array.from(summaries.values())
    ordered.sort((a, b) => {
      const severityWeight = { block: 0, warn: 1, info: 2 } as const
      const weightA = severityWeight[a.severity as keyof typeof severityWeight] ?? 1
      const weightB = severityWeight[b.severity as keyof typeof severityWeight] ?? 1
      if (weightA !== weightB) return weightA - weightB
      return a.category.localeCompare(b.category)
    })
    return ordered
  }, [showAllTurns, activeEvents, displayEvents])

  const metrics = useMemo(() => {
    const llmEvents = activeEvents.filter((event) => event.event_type === 'llm_response')
    const judgeEvents = activeEvents.filter((event) => event.event_type === 'judge_verdict')

    const latencySamples = llmEvents
      .map((event) => event.payload.latency_ms)
      .filter((value): value is number => typeof value === 'number')
    const latencySum = latencySamples.reduce((sum, value) => sum + value, 0)

    const contextSamples = llmEvents
      .map((event) => event.payload.context_tokens)
      .filter((value): value is number => typeof value === 'number')

    const totalJudge = judgeEvents.length
    let allowCount = 0
    let warnCount = 0
    let blockCount = 0
    judgeEvents.forEach((event) => {
      const verdict = (event.payload as JudgeVerdictPayload).verdict
      if (verdict === 'allow') allowCount += 1
      else if (verdict === 'warn') warnCount += 1
      else if (verdict === 'block') blockCount += 1
    })

    const weightedAgreement = allowCount + warnCount * 0.4
    const judgeAgreement =
      totalJudge === 0
        ? 'pending'
        : `${Math.round((weightedAgreement / totalJudge) * 100)}%`

    const violationCount = warnCount + blockCount

    const contextUsage = contextSamples.length
      ? `${Math.max(...contextSamples).toLocaleString()} tokens`
      : 'n/a'

    const metricsList = [
      {
        label: 'Average latency',
        value: formatLatency(latencySum, latencySamples.length),
        hint: 'Average response time for displayed turns.',
      },
      {
        label: 'Judge agreement',
        value: judgeAgreement,
        hint: 'Weighted score for displayed turns (allow = 1, warn = 0.4, block = 0). Shows “pending” until a verdict arrives.',
      },
      {
        label: 'Violations flagged',
        value: violationCount,
        hint: 'Number of warn/block verdicts across displayed turns.',
      },
      {
        label: 'Context usage',
        value: contextUsage,
        hint: 'Peak context window size observed for displayed base responses.',
      },
    ]
    return metricsList
  }, [activeEvents])

  const handleRevealRequest = useCallback(
    async ({ exchangeId, field }: { exchangeId: string; field: 'llm_response' | 'judge_rationale' }) => {
      if (!selectedRunId || usingDemoData) {
        throw new Error('Reveal logging unavailable in demo mode')
      }
      await recordReveal({
        runId: selectedRunId,
        exchangeId,
        field,
      })
    },
    [selectedRunId, usingDemoData],
  )

  const handlePromptSubmit = useCallback(
    async ({ prompt, scenarioId, judgeId }: ConsoleSubmitParams) => {
      setIsSubmitting(true)
      try {
        const result = await submitPrompt({ prompt, scenarioId, judgeId })
        queryClient.setQueryData<RunMetadata[]>(['runs'], (existing) => {
          const current = existing ?? []
          const filtered = current.filter((run) => run.run_id !== result.run.run_id)
          const merged = [result.run, ...filtered]
          return merged.sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
        })

        setStreamEvents((prev) => {
          const seen = new Set<string>()
          const merged = [...prev]
          merged.forEach((event) =>
            seen.add(`${event.event_type}|${event.exchange_id}|${event.created_at}`),
          )
          result.events.forEach((event) => {
            const key = `${event.event_type}|${event.exchange_id}|${event.created_at}`
            if (!seen.has(key)) {
              merged.push(event)
              seen.add(key)
            }
          })
          return merged
        })

        setSelectedRunId(result.run.run_id)
        setFiltersOpen(false)
        setIsPlaying(false)
        setShowAllTurns(false)
        setPlaybackIndex(result.events.length > 0 ? result.events.length - 1 : -1)
        setSelectedQuestionCategories(new Set())
        setSelectedViolationCategories(new Set())
      } catch (error) {
        console.error('Failed to submit prompt', error)
        throw error
      } finally {
        setIsSubmitting(false)
      }
    },
    [queryClient],
  )

  const handlePlay = useCallback(() => {
    if (filteredEvents.length === 0) return
    setIsPlaying(true)
    setShowAllTurns(false)
    setPlaybackIndex((prev) => {
      if (prev >= filteredEvents.length - 1 || prev < 0) {
        return 0
      }
      return prev
    })
  }, [filteredEvents.length])

  const handlePause = useCallback(() => {
    setIsPlaying(false)
  }, [])

  const handleStepForward = useCallback(() => {
    if (filteredEvents.length === 0) return
    setIsPlaying(false)
    setShowAllTurns(false)
    setPlaybackIndex((prev) => Math.min(prev + 1, filteredEvents.length - 1))
  }, [filteredEvents.length])

  const handleStepBack = useCallback(() => {
    if (filteredEvents.length === 0) return
    setIsPlaying(false)
    setShowAllTurns(false)
    setPlaybackIndex((prev) => Math.max(prev - 1, -1))
  }, [filteredEvents.length])

  const handleReset = useCallback(() => {
    setIsPlaying(false)
    setPlaybackIndex(-1)
    setShowAllTurns(false)
  }, [])

  const handleShowAll = useCallback(() => {
    setIsPlaying(false)
    setShowAllTurns((prev) => {
      if (prev) {
        return false
      }
      setPlaybackIndex(filteredEvents.length - 1)
      return true
    })
  }, [filteredEvents.length])

  const handleSpeedChange = useCallback((speed: number) => {
    setPlaybackSpeed(speed)
  }, [])

  const handleScrub = useCallback(
    (index: number) => {
      if (filteredEvents.length === 0) return
      const clamped = Math.min(Math.max(index, 0), filteredEvents.length - 1)
      setPlaybackIndex(clamped)
      setIsPlaying(false)
      setShowAllTurns(false)
    },
    [filteredEvents.length],
  )

  const currentRun =
    runsQuery.data?.find((run) => run.run_id === selectedRunId) ??
    activeEvents[0]?.run ??
    demoRun

  const isLiveRun = (currentRun.tags?.ui_live ?? '').toLowerCase() === 'true'

  const runBadgeText = usingDemoData
    ? 'Demo dataset'
    : `Run • ${currentRun.scenario_id ?? 'N/A'}`

  const runBadgeClass = usingDemoData
    ? 'border-gray-200 bg-gray-100 text-gray-600'
    : 'border-primary-200 bg-primary-50 text-primary-700'

  const streamIndicator = useMemo(() => {
    if (usingDemoData) {
      return {
        label: 'Offline replay',
        badgeClass: 'border-gray-200 bg-gray-100 text-gray-600',
        dotClass: 'bg-gray-400',
      }
    }
    if (streamStatus === 'connected') {
      return {
        label: 'Live updates',
        badgeClass: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        dotClass: 'bg-emerald-500',
      }
    }
    if (streamStatus === 'error') {
      return {
        label: 'Stream error – retrying',
        badgeClass: 'border-compliance-warn/40 bg-compliance-warn/10 text-compliance-warn',
        dotClass: 'bg-compliance-warn',
      }
    }
    return {
      label: 'Connecting…',
      badgeClass: 'border-primary-200 bg-primary-50 text-primary-700',
      dotClass: 'bg-primary-500',
    }
  }, [streamStatus, usingDemoData])

  const totalEvents = filteredEvents.length
  const displayedCount = showAllTurns ? activeEvents.length : Math.min(activeEvents.length, 1)
  const isTimelineLoading = timelineQuery.isLoading || timelineQuery.isFetching

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex w-full max-w-screen-2xl flex-col gap-4 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">CAM Agent Control Room</h1>
            <p className="text-sm text-gray-500">
              Monitoring interactions across base LLMs and judge reviewers.
            </p>
          </div>
          <div className="flex flex-col items-start gap-2 sm:items-end">
            <div
              className={`rounded-full border px-4 py-2 text-sm font-medium ${runBadgeClass}`}
            >
              {runBadgeText}
            </div>
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold ${streamIndicator.badgeClass}`}
            >
              <span className={`h-2 w-2 rounded-full ${streamIndicator.dotClass}`} />
              <span>{streamIndicator.label}</span>
            </div>
            <div className="text-xs text-gray-400">
              Started {new Date(currentRun.started_at).toLocaleString()}
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full px-6 py-6">
        <div
          className={
            isLiveRun
              ? 'flex flex-col gap-6'
              : 'grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,360px)]'
          }
        >
          <section className="flex flex-col gap-6">
          <RunSelector
            runs={runsQuery.data ?? []}
            selectedRunId={selectedRunId}
            onSelect={setSelectedRunId}
            isLoading={runsQuery.isLoading}
            error={runsQuery.isError ? (runsQuery.error as Error).message : null}
          />

          {timelineQuery.isError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-600">
              Failed to load timeline. Displaying demo data instead.
            </div>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Conversation Timeline</h2>
              <p className="text-sm text-gray-500">
                Animated flow of user prompts, LLM responses, and judge verdicts.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setFiltersOpen((prev) => !prev)}
              className="inline-flex items-center gap-2 self-start rounded-full border border-gray-200 px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm transition hover:border-primary-300 hover:text-primary-700 sm:self-auto"
            >
              <span className="inline-flex h-2 w-2 rounded-full bg-primary-500" />
              Filters
              {activeFilterCount > 0 && (
                <span className="rounded-full bg-primary-500/10 px-2 py-0.5 text-xs font-semibold text-primary-600">
                  {activeFilterCount}
                </span>
              )}
            </button>
          </div>

          {filtersOpen && (
            <div className="rounded-xl border border-gray-200 bg-white/95 p-4 shadow-sm backdrop-blur sm:hidden">
              <FilterPanel
                questionCategories={availableQuestionCategories}
                selectedQuestionCategories={selectedQuestionCategories}
                onToggleQuestion={(category) =>
                  setSelectedQuestionCategories((prev) => {
                    const next = new Set(prev)
                    if (next.has(category)) {
                      next.delete(category)
                    } else {
                      next.add(category)
                    }
                    return next
                  })
                }
                onClearQuestions={() => setSelectedQuestionCategories(new Set())}
                violationCategories={availableViolationCategories}
                selectedViolationCategories={selectedViolationCategories}
                onToggleViolation={(category) =>
                  setSelectedViolationCategories((prev) => {
                    const next = new Set(prev)
                    if (next.has(category)) {
                      next.delete(category)
                    } else {
                      next.add(category)
                    }
                    return next
                  })
                }
                onClearViolations={() => setSelectedViolationCategories(new Set())}
              />
            </div>
          )}

          <PlaybackControls
            isPlaying={isPlaying}
            playbackIndex={playbackIndex}
            totalEvents={totalEvents}
            displayedCount={displayedCount}
            playbackSpeed={playbackSpeed}
            showAll={showAllTurns}
            onPlay={handlePlay}
            onPause={handlePause}
            onStepForward={handleStepForward}
            onStepBack={handleStepBack}
            onReset={handleReset}
            onShowAll={handleShowAll}
            onSpeedChange={handleSpeedChange}
            onScrub={handleScrub}
          />

          <LiveConsole
            options={consoleOptionsQuery.data}
            selectedScenarioId={selectedScenarioOption}
            selectedJudgeId={selectedJudgeOption}
            onScenarioChange={(id) => setSelectedScenarioOption(id || null)}
            onJudgeChange={(id) => setSelectedJudgeOption(id || null)}
            onSubmit={handlePromptSubmit}
            isSubmitting={isSubmitting}
          />

          {!usingDemoData && streamStatus === 'error' && (
            <div className="rounded-xl border border-compliance-warn/40 bg-compliance-warn/10 p-4 text-sm text-compliance-warn">
              Live stream encountered an issue. Attempting to reconnect…
            </div>
          )}

          {totalEvents === 0 && !isTimelineLoading ? (
            <div className="rounded-xl border border-dashed border-gray-300 bg-white p-6 text-center text-sm text-gray-500 shadow-sm">
              No timeline events available yet for this run.
            </div>
          ) : (
            <Timeline
              events={displayEvents}
              allowReveal={!usingDemoData && Boolean(selectedRunId)}
              onReveal={handleRevealRequest}
            />
          )}
        </section>

        <aside className="flex flex-col gap-6">
          <div className={`${filtersOpen ? 'block sm:block' : 'hidden sm:block'}`}>
            <FilterPanel
              questionCategories={availableQuestionCategories}
              selectedQuestionCategories={selectedQuestionCategories}
              onToggleQuestion={(category) =>
                setSelectedQuestionCategories((prev) => {
                  const next = new Set(prev)
                  if (next.has(category)) {
                    next.delete(category)
                  } else {
                    next.add(category)
                  }
                  return next
                })
              }
              onClearQuestions={() => setSelectedQuestionCategories(new Set())}
              violationCategories={availableViolationCategories}
              selectedViolationCategories={selectedViolationCategories}
              onToggleViolation={(category) =>
                setSelectedViolationCategories((prev) => {
                  const next = new Set(prev)
                  if (next.has(category)) {
                    next.delete(category)
                  } else {
                    next.add(category)
                  }
                  return next
                })
              }
              onClearViolations={() => setSelectedViolationCategories(new Set())}
            />
          </div>

          <section>
            <h2 className="text-lg font-semibold text-gray-800">Run Metrics</h2>
            <MetricsPanel metrics={metrics} />
          </section>

        <section>
          <h2 className="text-lg font-semibold text-gray-800">Safety & Violations</h2>
          <SafetyPanel violations={safetyViolations} showHistory={showAllTurns} />
        </section>
      </aside>
      </div>
      </main>
    </div>
  )
}

export default App
