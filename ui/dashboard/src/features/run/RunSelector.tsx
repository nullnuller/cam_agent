import type { RunMetadata } from '../../types/events'

interface RunSelectorProps {
  runs: RunMetadata[]
  selectedRunId: string | null
  onSelect: (runId: string) => void
  isLoading?: boolean
  error?: string | null
}

export function RunSelector({
  runs,
  selectedRunId,
  onSelect,
  isLoading,
  error,
}: RunSelectorProps) {
  const disabled = runs.length === 0
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">Run Selection</h2>
        {isLoading && <span className="text-xs text-gray-400">Loading…</span>}
      </div>
      {error && (
        <div className="rounded-lg bg-red-50 p-2 text-xs text-red-600">
          Failed to load runs: {error}
        </div>
      )}
      <select
        className="rounded-lg border border-gray-200 bg-white p-2 text-sm text-gray-800 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
        value={selectedRunId ?? ''}
        onChange={(event) => onSelect(event.target.value)}
        disabled={disabled}
      >
        {disabled && <option value="">No runs available</option>}
        {runs.map((run) => (
          <option key={run.run_id} value={run.run_id}>
            {run.run_id} • {new Date(run.started_at).toLocaleString()}
          </option>
        ))}
      </select>
    </div>
  )
}
