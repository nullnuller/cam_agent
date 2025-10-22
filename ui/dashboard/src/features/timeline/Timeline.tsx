import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import type {
  TimelineEvent,
  LLMResponsePayload,
  JudgeVerdictPayload,
  RunMetadata,
  UserPromptPayload,
} from '../../types/events'

const verdictColor: Record<string, string> = {
  allow: 'bg-compliance-safe/20 text-compliance-safe border-compliance-safe/40',
  warn: 'bg-compliance-warn/20 text-compliance-warn border-compliance-warn/40',
  block: 'bg-compliance-block/20 text-compliance-block border-compliance-block/40',
}

type RevealField = 'llm_response' | 'judge_rationale'

interface TimelineProps {
  events: TimelineEvent<UserPromptPayload | LLMResponsePayload | JudgeVerdictPayload>[]
  allowReveal?: boolean
  onReveal?: (details: { exchangeId: string; field: RevealField }) => Promise<void> | void
}

interface TurnGroup {
  exchangeId: string
  turnIndex: number
  createdAt: string
  run: RunMetadata
  userPrompt?: UserPromptPayload
  response?: LLMResponsePayload
  judges: JudgeVerdictPayload[]
}

const groupVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0 },
}

const cardVariants = {
  hidden: { opacity: 0, scale: 0.98 },
  visible: { opacity: 1, scale: 1 },
}

const verdictBadge = (verdict?: string | null) =>
  verdict ? verdictColor[verdict] ?? 'bg-gray-200' : 'bg-gray-100 text-gray-600 border-gray-200'

export function Timeline({ events, allowReveal = false, onReveal }: TimelineProps) {
  const runKey = events.length > 0 ? events[0].run.run_id : 'none'
  const groups = useMemo(() => {
    const collection: TurnGroup[] = []
    const map = new Map<string, TurnGroup>()

    events.forEach((event) => {
      let entry = map.get(event.exchange_id)
      if (!entry) {
        entry = {
          exchangeId: event.exchange_id,
          turnIndex: event.turn_index,
          createdAt: event.created_at,
          run: event.run,
          judges: [],
        }
        map.set(event.exchange_id, entry)
        collection.push(entry)
      }
      entry.createdAt = event.created_at
      if (event.event_type === 'user_prompt') {
        entry.userPrompt = event.payload as UserPromptPayload
      } else if (event.event_type === 'llm_response') {
        entry.response = event.payload as LLMResponsePayload
      } else if (event.event_type === 'judge_verdict') {
        entry.judges.push(event.payload as JudgeVerdictPayload)
      }
    })

    return collection
  }, [events])

  const [expandedMap, setExpandedMap] = useState<Record<string, boolean>>({})
  const [stageMap, setStageMap] = useState<Record<string, number>>({})
  const stageRef = useRef<Record<string, number>>({})
  const pendingStageRef = useRef<Set<string>>(new Set())
  const pendingJudgeRef = useRef<Set<string>>(new Set())
  const [revealedMap, setRevealedMap] = useState<
    Record<string, { response?: boolean; rationale?: boolean }>
  >({})
  const [revealErrors, setRevealErrors] = useState<Record<string, string | null>>({})
  const [pendingReveal, setPendingReveal] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setExpandedMap({})
    setStageMap({})
    stageRef.current = {}
    pendingStageRef.current.clear()
    pendingJudgeRef.current.clear()
    setRevealedMap({})
    setRevealErrors({})
    setPendingReveal({})
  }, [runKey])

  const liveMode = useMemo(
    () =>
      groups.some(
        (group) => ((group.run.tags?.ui_live ?? '').toLowerCase() === 'true'),
      ),
    [groups],
  )

  useEffect(() => {
    if (!groups.length) {
      return
    }

    if (!liveMode) {
      let changed = false
      setStageMap((prev) => {
        const next = { ...prev }
        groups.forEach((group) => {
          if (next[group.exchangeId] !== 2) {
            next[group.exchangeId] = 2
            changed = true
          }
          stageRef.current[group.exchangeId] = 2
        })
        return changed ? next : prev
      })
      pendingStageRef.current.clear()
      pendingJudgeRef.current.clear()
      return
    }

    const timers: ReturnType<typeof setTimeout>[] = []

    groups.forEach((group, index) => {
      const id = group.exchangeId
      const baseDelay = 260 + index * 120
      const currentStage = stageRef.current[id]
      const hasResponse = Boolean(group.response)
      const hasJudgeVerdict = group.judges.length > 0

      if (currentStage === undefined) {
        stageRef.current[id] = 0
        setStageMap((prev) => {
          if (prev[id] === 0) return prev
          return { ...prev, [id]: 0 }
        })
      }

      if (
        hasResponse &&
        (stageRef.current[id] ?? 0) < 1 &&
        !pendingStageRef.current.has(id)
      ) {
        pendingStageRef.current.add(id)
        timers.push(
          setTimeout(() => {
            pendingStageRef.current.delete(id)
            const nextStage = Math.max(stageRef.current[id] ?? 0, 1)
            stageRef.current[id] = nextStage
            setStageMap((prev) => {
              const existing = prev[id]
              if (existing !== undefined && existing >= nextStage) {
                return prev
              }
              return { ...prev, [id]: nextStage }
            })
          }, baseDelay),
        )
      }

      if (
        hasJudgeVerdict &&
        (stageRef.current[id] ?? 0) < 2 &&
        !pendingJudgeRef.current.has(id)
      ) {
        pendingJudgeRef.current.add(id)
        timers.push(
          setTimeout(() => {
            pendingJudgeRef.current.delete(id)
            stageRef.current[id] = 2
            setStageMap((prev) => {
              const existing = prev[id]
              if (existing !== undefined && existing >= 2) {
                return prev
              }
              return { ...prev, [id]: 2 }
            })
          }, baseDelay + 320),
        )
      }
    })

    return () => {
      timers.forEach((timer) => clearTimeout(timer))
    }
  }, [groups, liveMode])

  if (groups.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-center text-sm text-gray-500">
        Playback or filter to reveal interactions.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <AnimatePresence initial={false}>
        {groups.map((group) => {
          const createdTime = new Date(group.createdAt).toLocaleTimeString()
          const stage = stageMap[group.exchangeId] ?? (liveMode ? 0 : 2)
          const primaryJudge = group.judges[group.judges.length - 1] ?? null
          const responsePayload = group.response
          const promptPayload = group.userPrompt
          const severity = primaryJudge?.verdict
          const judgeTone =
            severity === 'block'
              ? 'border-compliance-block/70 bg-compliance-block/15'
            : severity === 'warn'
              ? 'border-compliance-warn/60 bg-compliance-warn/10'
              : 'border-gray-100 bg-white'
          const judgeGlow =
            severity === 'block'
              ? { boxShadow: '0 0 0 3px rgba(247,129,84,0.28)' }
            : severity === 'warn'
              ? { boxShadow: '0 0 0 3px rgba(242,193,78,0.24)' }
              : { boxShadow: '0 0 0 0 rgba(0,0,0,0)' }
          const userStageClass =
            stage === 0
              ? 'ring-2 ring-primary-400/70 shadow-lg shadow-primary-400/30'
              : 'border-gray-100'
          const llmStageClass =
            stage < 1
              ? 'opacity-45 saturate-75'
              : stage === 1
              ? 'ring-2 ring-primary-400/70 shadow-lg shadow-primary-300/40'
              : 'border-primary-100 bg-primary-50/50 shadow-primary-200/30'
          const judgeStageClass =
            stage < 2
              ? 'opacity-45 saturate-75'
              : 'ring-2 ring-compliance-safe/60 shadow-lg shadow-compliance-safe/30'
          const isExpanded = expandedMap[group.exchangeId] ?? false
          const toggleExpanded = () =>
            setExpandedMap((prev) => ({
              ...prev,
              [group.exchangeId]: !isExpanded,
            }))
          const responseState = revealedMap[group.exchangeId] ?? {}
          const isResponseRevealed = Boolean(responseState.response)
          const revealError = revealErrors[group.exchangeId] ?? null
          const isRevealPending = Boolean(pendingReveal[group.exchangeId])
          const hasRawResponse = Boolean(responsePayload?.pii_raw_text)
          const responseText = responsePayload
            ? isResponseRevealed && responsePayload.pii_raw_text
              ? responsePayload.pii_raw_text
              : responsePayload.pii_redacted_text ?? 'Awaiting response…'
            : 'Awaiting model response…'
          const questionCategory =
            promptPayload?.question_category ?? responsePayload?.question_category ?? null
          const piiFields =
            Array.isArray(responsePayload?.pii_fields) && responsePayload?.pii_fields
              ? (responsePayload?.pii_fields as string[])
              : []
          const promptText =
            promptPayload?.prompt_redacted ??
            promptPayload?.prompt_text ??
            responsePayload?.prompt_preview ??
            'Awaiting submission…'

          const handleRevealResponse = async () => {
            if (!onReveal) {
              setRevealErrors((prev) => ({
                ...prev,
                [group.exchangeId]: 'Reveal logging unavailable.',
              }))
              return
            }
            if (!allowReveal) {
              setRevealErrors((prev) => ({
                ...prev,
                [group.exchangeId]: 'Reveals disabled in demo mode.',
              }))
              return
            }
            if (!responsePayload) {
              setRevealErrors((prev) => ({
                ...prev,
                [group.exchangeId]: 'Model response not available yet.',
              }))
              return
            }
            if (!responsePayload.pii_raw_text) {
              setRevealErrors((prev) => ({
                ...prev,
                [group.exchangeId]: 'Full response not available.',
              }))
              return
            }
            setPendingReveal((prev) => ({ ...prev, [group.exchangeId]: true }))
            try {
              await onReveal({ exchangeId: group.exchangeId, field: 'llm_response' })
              setRevealedMap((prev) => ({
                ...prev,
                [group.exchangeId]: { ...(prev[group.exchangeId] ?? {}), response: true },
              }))
              setRevealErrors((prev) => ({ ...prev, [group.exchangeId]: null }))
            } catch (error) {
              console.error(error)
              setRevealErrors((prev) => ({
                ...prev,
                [group.exchangeId]: 'Failed to log reveal. Please retry.',
              }))
            } finally {
              setPendingReveal((prev) => ({ ...prev, [group.exchangeId]: false }))
            }
          }

          return (
            <motion.div
              key={group.exchangeId}
              variants={groupVariants}
              initial="hidden"
              animate="visible"
              exit="hidden"
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="grid gap-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm md:grid-cols-1 lg:grid-cols-2 xl:grid-cols-[minmax(260px,1fr)_minmax(360px,1.6fr)_minmax(260px,1fr)]"
            >
              <motion.div
                variants={cardVariants}
                transition={{ duration: 0.25, delay: 0.05 }}
                className={`rounded-2xl border bg-gray-50 p-4 text-sm shadow-inner transition-all duration-500 ${userStageClass}`}
              >
                <div className="flex items-center justify-between text-xs font-semibold uppercase text-gray-500">
                  <span>User Query</span>
                  <span className="text-gray-400">Turn {group.turnIndex + 1}</span>
                </div>
                {questionCategory && (
                  <span className="mt-3 inline-flex items-center rounded-full bg-primary-50 px-2 py-1 text-xs font-semibold text-primary-700">
                    {questionCategory}
                  </span>
                )}
                <p
                  className={`mt-3 whitespace-pre-wrap text-gray-700 ${
                    isExpanded ? '' : 'max-h-40 overflow-hidden'
                  }`}
                >
                  {promptText}
                </p>
              </motion.div>

              <motion.div
                variants={cardVariants}
                transition={{ duration: 0.25, delay: 0.1 }}
                className={`rounded-2xl border border-primary-100 bg-primary-50/40 p-4 text-sm shadow-sm transition-all duration-500 ${llmStageClass}`}
              >
                <div className="flex items-center justify-between text-xs font-semibold uppercase text-primary-700">
                  <span>LLM Response</span>
                  <span>{responsePayload?.source.model_id ?? '—'}</span>
                </div>
                <p
                  className={`mt-3 whitespace-pre-wrap text-gray-800 ${
                    isExpanded ? '' : 'max-h-48 overflow-hidden'
                  }`}
                >
                  {responseText}
                </p>
                {responsePayload && piiFields.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
                    {piiFields.map((field, index) => (
                      <span
                        key={`${group.exchangeId}-pii-${index}`}
                        className="rounded-full border border-gray-200 px-2 py-1"
                      >
                        {field}
                      </span>
                    ))}
                  </div>
                )}
                {responsePayload && (hasRawResponse || revealError || isResponseRevealed) && (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500">
                    {allowReveal && hasRawResponse && !isResponseRevealed && (
                      <button
                        type="button"
                        onClick={handleRevealResponse}
                        disabled={isRevealPending}
                        className="rounded-full border border-primary-300 px-3 py-1 font-semibold text-primary-600 transition hover:border-primary-400 hover:text-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isRevealPending ? 'Revealing…' : 'Reveal full response'}
                      </button>
                    )}
                    {!allowReveal && hasRawResponse && !isResponseRevealed && (
                      <span className="text-gray-400">Reveals disabled in demo mode.</span>
                    )}
                    {isResponseRevealed && (
                      <span className="font-semibold text-primary-600">Full response revealed</span>
                    )}
                    {revealError && (
                      <span className="text-compliance-block">{revealError}</span>
                    )}
                  </div>
                )}
                {!responsePayload && (
                  <div className="mt-3 text-xs text-gray-400">Awaiting model response…</div>
                )}
                {!hasRawResponse && responsePayload?.pii_redacted_text && !isResponseRevealed && (
                  <div className="mt-3 text-xs text-gray-400">
                    Response provided in redacted form.
                  </div>
                )}
              </motion.div>

              <motion.div
                variants={cardVariants}
                transition={{ duration: 0.25, delay: 0.15 }}
                animate={judgeGlow}
                className={`rounded-2xl p-4 text-sm shadow-lg transition-all duration-500 ${judgeTone} ${judgeStageClass}`}
              >
                <div className="flex items-center justify-between text-xs font-semibold uppercase text-gray-500">
                  <span>Judge Verdict</span>
                  <span className="text-gray-400">{createdTime}</span>
                </div>
                {group.judges.length === 0 ? (
                  <p className="mt-3 text-sm text-gray-500">Awaiting verdict…</p>
                ) : (
                  <div className="mt-3 space-y-3">
                    {group.judges.map((judge, index) => (
                      <motion.div
                        key={`${judge.source.model_id}-${index}-${judge.verdict}`}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.25, delay: 0.1 * index }}
                        className="rounded-xl bg-white/70 p-3 shadow-sm"
                      >
                        <div className="flex items-center justify-between text-xs font-semibold uppercase">
                          <span className={`rounded-full border px-2 py-1 ${verdictBadge(judge.verdict)}`}>
                            Verdict: {judge.verdict}
                          </span>
                          {judge.source?.model_id && (
                            <span className="rounded-full bg-primary-50 px-2 py-1 text-primary-700">
                              {judge.source.model_id}
                            </span>
                          )}
                        </div>
                        {judge.rationale_redacted && (
                          <p className="mt-3 text-sm text-gray-600">{judge.rationale_redacted}</p>
                        )}
                        {judge.violation && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            <span className="rounded-full bg-compliance-warn/20 px-3 py-1 text-xs font-semibold text-compliance-warn">
                              {judge.violation.category}
                            </span>
                            {judge.violation.violation_type && (
                              <span className="rounded-full border border-compliance-warn/40 px-3 py-1 text-xs font-semibold text-compliance-warn">
                                {judge.violation.violation_type}
                              </span>
                            )}
                            {judge.violation.clause_reference && (
                              <span className="rounded-full border border-gray-200 px-3 py-1 text-xs font-semibold text-gray-600">
                                {judge.violation.clause_reference}
                              </span>
                            )}
                          </div>
                        )}
                      </motion.div>
                    ))}
                  </div>
                )}
                <div className="mt-3 text-right">
                  <button
                    type="button"
                    onClick={toggleExpanded}
                    className="text-xs font-semibold text-primary-600 hover:text-primary-700"
                  >
                    {isExpanded ? 'Show less' : 'Show more'}
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )
        })}
      </AnimatePresence>
    </div>
  )
}
