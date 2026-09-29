/**
 * Shared chart primitives, same pattern as Mandate360's
 * frontend/mandate360-portal/src/components/charts.tsx — hand-rolled
 * inline SVG rather than a charting library. Color follows the dataviz
 * skill's method: fixed-order categorical palette, single-hue sequential
 * ramp, reserved status palette.
 */
import type { ReactNode } from "react"

export const CATEGORICAL = ["#0B2447", "#1E8F6F", "#1C7ED6", "#C9762B", "#e87ba4", "#4a3aa7"]
export const STATUS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" }

const INK_PRIMARY = "var(--foreground, #0b0b0b)"
const INK_MUTED = "var(--muted-foreground, #898781)"
const GRID = "#e1e0d9"

export function StatTile({ label, value, sub, accent }: { label: string; value: ReactNode; sub?: ReactNode; accent?: string }) {
  return (
    <div className="rounded-lg border p-4 space-y-1" style={accent ? { borderTopColor: accent, borderTopWidth: 3 } : undefined}>
      <p className="text-xs uppercase text-muted-foreground tracking-wide">{label}</p>
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  )
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  if (items.length < 2) return null
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((it) => (
        <span key={it.label} className="flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: it.color }} />
          {it.label}
        </span>
      ))}
    </div>
  )
}

export function BarChart({ data, height = 22, formatValue }: {
  data: { label: string; value: number; color?: string }[]
  height?: number
  formatValue?: (v: number) => string
}) {
  const max = Math.max(1, ...data.map((d) => d.value))
  const fmt = formatValue ?? ((v: number) => v.toLocaleString("en-IN"))
  if (data.length === 0) return <p className="text-sm text-muted-foreground py-4 text-center">No data.</p>
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={d.label} className="flex items-center gap-2">
          <span className="w-32 shrink-0 truncate text-xs text-muted-foreground" title={d.label}>{d.label}</span>
          <div className="flex-1 rounded-sm overflow-hidden" style={{ backgroundColor: GRID, height }}>
            <div
              className="h-full rounded-sm transition-all"
              style={{ width: `${Math.max(2, (d.value / max) * 100)}%`, backgroundColor: d.color ?? CATEGORICAL[i % CATEGORICAL.length] }}
              title={`${d.label}: ${fmt(d.value)}`}
            />
          </div>
          <span className="w-16 shrink-0 text-right text-xs tabular-nums">{fmt(d.value)}</span>
        </div>
      ))}
    </div>
  )
}

export function DonutChart({ data, size = 160, formatValue }: {
  data: { label: string; value: number; color?: string }[]
  size?: number
  formatValue?: (v: number) => string
}) {
  const total = data.reduce((a, d) => a + d.value, 0)
  const fmt = formatValue ?? ((v: number) => v.toLocaleString("en-IN"))
  if (total <= 0) return <p className="text-sm text-muted-foreground py-4 text-center">No data.</p>

  const radius = size / 2
  const stroke = radius * 0.4
  const r = radius - stroke / 2
  const circumference = 2 * Math.PI * r
  let offset = 0

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Distribution donut chart">
        <circle cx={radius} cy={radius} r={r} fill="none" stroke={GRID} strokeWidth={stroke} />
        {data.map((d, i) => {
          const frac = d.value / total
          const dash = frac * circumference
          const el = (
            <circle
              key={d.label}
              cx={radius} cy={radius} r={r} fill="none"
              stroke={d.color ?? CATEGORICAL[i % CATEGORICAL.length]}
              strokeWidth={stroke}
              strokeDasharray={`${Math.max(0, dash - 2)} ${circumference - dash + 2}`}
              strokeDashoffset={-offset}
              transform={`rotate(-90 ${radius} ${radius})`}
              strokeLinecap="butt"
            >
              <title>{`${d.label}: ${fmt(d.value)} (${Math.round(frac * 100)}%)`}</title>
            </circle>
          )
          offset += dash
          return el
        })}
        <text x={radius} y={radius - 4} textAnchor="middle" fontSize={size * 0.14} fontWeight={700} fill={INK_PRIMARY}>
          {total.toLocaleString("en-IN")}
        </text>
        <text x={radius} y={radius + 14} textAnchor="middle" fontSize={size * 0.075} fill={INK_MUTED}>total</text>
      </svg>
      <Legend items={data.map((d, i) => ({ label: `${d.label} (${Math.round((d.value / total) * 100)}%)`, color: d.color ?? CATEGORICAL[i % CATEGORICAL.length] }))} />
    </div>
  )
}
