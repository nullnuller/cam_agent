import type { ViolationDetail } from '../../types/events'

interface ViolationSummary extends ViolationDetail {
  count: number
}

interface SafetyPanelProps {
  violations: ViolationSummary[]
  showHistory: boolean
}

const severityColor: Record<string, string> = {
  info: 'text-primary-700 border-primary-100 bg-primary-50',
  warn: 'text-compliance-warn border-compliance-warn/40 bg-compliance-warn/10',
  block: 'text-compliance-block border-compliance-block/40 bg-compliance-block/10',
}

export function SafetyPanel({ violations, showHistory }: SafetyPanelProps) {
  if (!violations.length) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-600 shadow-sm">
        No violations detected for this run.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="text-xs font-medium text-gray-500">
        {showHistory
          ? 'Aggregated safety findings across displayed turns.'
          : 'Latest turn safety findings.'}
      </div>
      {violations.map((violation, index) => (
        <div
          key={`${violation.category}-${index}`}
          className={`rounded-xl border p-4 text-sm shadow-sm ${severityColor[violation.severity] ?? 'bg-gray-50'}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-semibold">{violation.category}</span>
              {violation.count > 1 && (
                <span className="rounded-full bg-white/60 px-2 py-0.5 text-xs font-semibold text-gray-600">
                  ×{violation.count}
                </span>
              )}
            </div>
            {violation.clause_reference && (
              <span className="text-xs uppercase text-gray-500">
                {violation.clause_reference}
              </span>
            )}
          </div>
          {violation.violation_type && (
            <div className="mt-2 text-xs uppercase tracking-wide text-gray-500">
              {violation.violation_type}
            </div>
          )}
          {violation.description && (
            <p className="mt-2 text-gray-600">{violation.description}</p>
          )}
        </div>
      ))}
    </div>
  )
}
