interface Metric {
  label: string
  value: string | number
  delta?: string
  hint?: string
}

interface MetricsPanelProps {
  metrics: Metric[]
}

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="flex items-center justify-between text-sm font-semibold text-gray-500">
            <span>{metric.label}</span>
            {metric.hint && (
              <span
                className="cursor-help text-xs font-medium text-gray-400"
                title={metric.hint}
                aria-label={metric.hint}
              >
                ⓘ
              </span>
            )}
          </div>
          <div className="mt-2 text-2xl font-semibold text-gray-900">{metric.value}</div>
          {metric.delta && (
            <div className="text-xs text-gray-400">Δ {metric.delta}</div>
          )}
        </div>
      ))}
    </div>
  )
}
