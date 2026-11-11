import type { CSSProperties } from 'react'

export function Skeleton({
  width,
  height = 16,
  radius,
  className,
  style,
}: {
  width?: number | string
  height?: number | string
  radius?: number | string
  className?: string
  style?: CSSProperties
}) {
  return (
    <span
      aria-hidden="true"
      className={`skeleton ${className ?? ''}`.trim()}
      style={{ display: 'block', width, height, borderRadius: radius, ...style }}
    />
  )
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }} aria-hidden="true">
      <Skeleton width="55%" height={22} />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={`${90 - i * 12}%`} height={14} />
      ))}
    </div>
  )
}
