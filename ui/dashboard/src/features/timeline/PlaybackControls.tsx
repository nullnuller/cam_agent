interface PlaybackControlsProps {
  isPlaying: boolean
  playbackIndex: number
  totalEvents: number
  displayedCount: number
  playbackSpeed: number
  showAll: boolean
  onPlay: () => void
  onPause: () => void
  onStepForward: () => void
  onStepBack: () => void
  onReset: () => void
  onShowAll: () => void
  onSpeedChange: (speed: number) => void
  onScrub: (index: number) => void
}

const speedOptions = [0.5, 1, 1.5, 2]

export function PlaybackControls({
  isPlaying,
  playbackIndex,
  totalEvents,
  displayedCount,
  playbackSpeed,
  showAll,
  onPlay,
  onPause,
  onStepForward,
  onStepBack,
  onReset,
  onShowAll,
  onSpeedChange,
  onScrub,
}: PlaybackControlsProps) {
  const disabled = totalEvents === 0
  const sliderValue = totalEvents === 0 ? 0 : Math.max(playbackIndex, 0)
  const sliderMax = totalEvents === 0 ? 0 : totalEvents - 1

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onPlay}
          disabled={disabled || isPlaying}
          className="rounded-full bg-primary-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary-700 disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          Play
        </button>
        <button
          type="button"
          onClick={onPause}
          disabled={disabled || !isPlaying}
          className="rounded-full border border-gray-200 px-4 py-1.5 text-sm font-semibold text-gray-700 shadow-sm transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Pause
        </button>
        <button
          type="button"
          onClick={onStepBack}
          disabled={disabled || playbackIndex <= -1}
          className="rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          ‹ Prev
        </button>
        <button
          type="button"
          onClick={onStepForward}
          disabled={disabled || playbackIndex >= totalEvents - 1}
          className="rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Next ›
        </button>
        <button
          type="button"
          onClick={onReset}
          disabled={disabled}
          className="rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Reset
        </button>
        <button
          type="button"
          onClick={onShowAll}
          disabled={disabled}
          className="rounded-full border border-gray-200 px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:border-gray-300 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {showAll ? 'Collapse' : 'Show All'}
        </button>
      </div>

      <div className="flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={sliderMax}
          value={sliderValue}
          onChange={(event) => onScrub(Number(event.target.value))}
          disabled={disabled}
          className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-gray-200 accent-primary-500 disabled:cursor-not-allowed"
        />
        <span className="text-xs font-medium text-gray-500">
          {displayedCount}/{totalEvents}
        </span>
      </div>

      <div className="flex items-center gap-2 text-sm text-gray-600">
        <span>Speed</span>
        <select
          className="rounded-lg border border-gray-200 bg-white px-3 py-1 text-sm text-gray-700 focus:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-100"
          value={playbackSpeed}
          onChange={(event) => onSpeedChange(Number(event.target.value))}
          disabled={disabled}
        >
          {speedOptions.map((speed) => (
            <option key={speed} value={speed}>
              {speed}×
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}
