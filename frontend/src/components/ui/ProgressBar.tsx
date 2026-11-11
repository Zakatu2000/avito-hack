export function ProgressBar({
  value,
  max = 100,
  label,
  className,
}: {
  value: number
  max?: number
  label: string
  className?: string
}) {
  const clamped = Math.max(0, Math.min(max, value))
  return (
    <div
      className={`progress ${className ?? ''}`.trim()}
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
    >
      <div className="progress__fill" style={{ width: `${(clamped / max) * 100}%` }} />
    </div>
  )
}
