import { useMemo, useState } from 'react'
import type { ConsoleOptions } from '../../lib/api'

interface LiveConsoleProps {
  options?: ConsoleOptions
  selectedScenarioId: string | null
  selectedJudgeId: string | null
  onScenarioChange: (scenarioId: string) => void
  onJudgeChange: (judgeId: string) => void
  onSubmit: (payload: { prompt: string; scenarioId: string; judgeId: string }) => Promise<void>
  isSubmitting?: boolean
}

export function LiveConsole({
  options,
  selectedScenarioId,
  selectedJudgeId,
  onScenarioChange,
  onJudgeChange,
  onSubmit,
  isSubmitting,
}: LiveConsoleProps) {
  const [prompt, setPrompt] = useState('')
  const [status, setStatus] = useState<string | null>(null)

  const scenarioOption = useMemo(
    () => options?.scenarios.find((option) => option.id === selectedScenarioId) ?? null,
    [options, selectedScenarioId],
  )

  const judgeOption = useMemo(
    () => options?.judges.find((option) => option.id === selectedJudgeId) ?? null,
    [options, selectedJudgeId],
  )

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!prompt.trim()) return
    if (!selectedScenarioId || !options?.scenarios.some((option) => option.id === selectedScenarioId)) {
      setStatus('Select a base LLM before sending.')
      return
    }
    if (!selectedJudgeId) {
      setStatus('Select a judge option before sending.')
      return
    }
    try {
      setStatus('Sending…')
      await onSubmit({ prompt, scenarioId: selectedScenarioId, judgeId: selectedJudgeId })
      setStatus('Submitted for evaluation')
      setPrompt('')
    } catch (error) {
      console.error(error)
      setStatus('Failed to submit prompt')
    }
  }

  const canSubmit = Boolean(
    selectedScenarioId &&
      selectedJudgeId &&
      (!judgeOption || judgeOption.id === 'none' || judgeOption.available),
  )

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <h3 className="text-base font-semibold text-gray-800">Realtime Query</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="block text-sm font-medium text-gray-600">
          Query LLM
          <select
            className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
            value={selectedScenarioId ?? ''}
            onChange={(event) => onScenarioChange(event.target.value)}
            disabled={!options || options.scenarios.length === 0}
          >
            <option value="" disabled>
              Select base model…
            </option>
            {options?.scenarios.map((scenario) => (
              <option key={scenario.id} value={scenario.id}>
                {scenario.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm font-medium text-gray-600">
          Judge LLM
          <select
            className="mt-2 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-800 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
            value={selectedJudgeId ?? ''}
            onChange={(event) => onJudgeChange(event.target.value)}
            disabled={!options || options.judges.length === 0}
          >
            <option value="" disabled>
              Select judge model…
            </option>
            {options?.judges.map((judge) => (
              <option key={judge.id} value={judge.id} disabled={!judge.available}>
                {judge.label}
                {!judge.available ? ' (configure to enable)' : ''}
              </option>
            ))}
          </select>
        </label>
      </div>
      {scenarioOption && (
        <p className="mt-2 text-xs text-gray-500">
          Using {scenarioOption.model}
          {scenarioOption.use_rag ? ' with RAG context.' : ' without RAG.'}
        </p>
      )}
      {judgeOption && judgeOption.id !== 'none' && (
        <p className="mt-1 text-xs text-gray-500">
          Judge: {judgeOption.label}
          {judgeOption.description ? ` — ${judgeOption.description}` : ''}
        </p>
      )}
      <label className="mt-3 block text-sm font-medium text-gray-600">
        Prompt
        <textarea
          className="mt-2 w-full rounded-lg border border-gray-200 bg-white p-3 text-sm text-gray-800 shadow-inner focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
          rows={4}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          placeholder="Ask the CAM agent about a healthcare policy…"
        />
      </label>
      <div className="mt-3 flex items-center justify-between text-sm text-gray-500">
        <button
          type="submit"
          disabled={isSubmitting || !canSubmit}
          className="rounded-full bg-primary-600 px-4 py-2 font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {isSubmitting ? 'Submitting…' : 'Send to CAM'}
        </button>
        {status && <span>{status}</span>}
      </div>
    </form>
  )
}
