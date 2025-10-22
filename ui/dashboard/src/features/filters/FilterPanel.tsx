interface FilterPanelProps {
  questionCategories: string[]
  selectedQuestionCategories: Set<string>
  onToggleQuestion: (category: string) => void
  onClearQuestions: () => void
  violationCategories: string[]
  selectedViolationCategories: Set<string>
  onToggleViolation: (category: string) => void
  onClearViolations: () => void
}

function renderPill(
  label: string,
  isActive: boolean,
  onClick: () => void,
) {
  const base =
    'rounded-full border px-3 py-1 text-xs font-semibold transition-colors'
  const active = isActive
    ? 'border-primary-500 bg-primary-100 text-primary-700'
    : 'border-gray-200 bg-white text-gray-600 hover:border-primary-200'
  return (
    <button
      key={label}
      type="button"
      className={`${base} ${active}`}
      onClick={onClick}
    >
      {label}
    </button>
  )
}

export function FilterPanel({
  questionCategories,
  selectedQuestionCategories,
  onToggleQuestion,
  onClearQuestions,
  violationCategories,
  selectedViolationCategories,
  onToggleViolation,
  onClearViolations,
}: FilterPanelProps) {
  const hasQuestionFilters = questionCategories.length > 0
  const hasViolationFilters = violationCategories.length > 0

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">Filters</h2>
        {(selectedQuestionCategories.size > 0 ||
          selectedViolationCategories.size > 0) && (
          <button
            type="button"
            className="text-xs font-semibold text-primary-600 hover:text-primary-700"
            onClick={() => {
              onClearQuestions()
              onClearViolations()
            }}
          >
            Clear all
          </button>
        )}
      </div>

      {hasQuestionFilters && (
        <section className="mt-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-500">
              Question Category
            </span>
            {selectedQuestionCategories.size > 0 && (
              <button
                type="button"
                className="text-xs text-primary-500 hover:text-primary-600"
                onClick={onClearQuestions}
              >
                Reset
              </button>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {questionCategories.map((category) =>
              renderPill(category, selectedQuestionCategories.has(category), () =>
                onToggleQuestion(category),
              ),
            )}
          </div>
        </section>
      )}

      {hasViolationFilters && (
        <section className="mt-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-gray-500">
              Violation Category
            </span>
            {selectedViolationCategories.size > 0 && (
              <button
                type="button"
                className="text-xs text-primary-500 hover:text-primary-600"
                onClick={onClearViolations}
              >
                Reset
              </button>
            )}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {violationCategories.map((category) =>
              renderPill(category, selectedViolationCategories.has(category), () =>
                onToggleViolation(category),
              ),
            )}
          </div>
        </section>
      )}
    </div>
  )
}
