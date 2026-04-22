'use client'

import type { MetricsDelta, ScenarioMetrics, Scenario } from '@/types'

interface Props {
  before: ScenarioMetrics
  after: ScenarioMetrics
  delta: MetricsDelta
  scenario: Scenario
}

interface MetricCardProps {
  label: string
  beforeVal: string
  afterVal: string
  badge: string
  good: boolean
}

function MetricCard({ label, beforeVal, afterVal, badge, good }: MetricCardProps) {
  return (
    <div className="rounded-lg bg-gray-800 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-1.5">
        {label}
      </p>
      <div className="flex items-end justify-between gap-2">
        <div>
          <p className="text-xl font-bold text-white leading-none">{afterVal}</p>
          <p className="text-[11px] text-gray-500 mt-0.5">was {beforeVal}</p>
        </div>
        <span
          className={`text-[11px] font-semibold px-2 py-0.5 rounded-full flex-shrink-0 ${
            good
              ? 'bg-green-900/60 text-green-400'
              : 'bg-red-900/60 text-red-400'
          }`}
        >
          {badge}
        </span>
      </div>
    </div>
  )
}

function fmt(n: number, decimals = 0) {
  return n.toLocaleString('en-US', { maximumFractionDigits: decimals })
}

export default function MetricsPanel({ before, after, delta }: Props) {
  return (
    <section>
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500 mb-2">
        Impact Metrics
      </h2>

      <div className="grid grid-cols-2 gap-2">
        <MetricCard
          label="Fleet size"
          beforeVal={`${before.num_routes} buses`}
          afterVal={`${after.num_routes} buses`}
          badge={`−${delta.routes_eliminated}`}
          good={delta.routes_eliminated > 0}
        />
        <MetricCard
          label="Avg utilization"
          beforeVal={`${(before.avg_load_factor * 100).toFixed(0)}%`}
          afterVal={`${(after.avg_load_factor * 100).toFixed(0)}%`}
          badge={`+${(delta.load_factor_improvement * 100).toFixed(0)}pp`}
          good={delta.load_factor_improvement > 0}
        />
        <MetricCard
          label="Daily distance"
          beforeVal={`${fmt(before.total_distance_km, 1)} km`}
          afterVal={`${fmt(after.total_distance_km, 1)} km`}
          badge={`−${delta.distance_saved_pct.toFixed(0)}%`}
          good={delta.distance_saved_km > 0}
        />
        <MetricCard
          label="CO₂ / day"
          beforeVal={`${fmt(before.total_co2_kg, 0)} kg`}
          afterVal={`${fmt(after.total_co2_kg, 0)} kg`}
          badge={`−${fmt(delta.co2_saved_kg_daily, 0)} kg`}
          good={delta.co2_saved_kg_daily > 0}
        />
      </div>

      {/* Annual savings highlight */}
      <div className="mt-2 rounded-lg bg-green-900/30 border border-green-800 p-3 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-green-500">
            Est. Annual Savings
          </p>
          <p className="text-2xl font-bold text-green-400 mt-0.5">
            ${delta.estimated_annual_savings_usd.toLocaleString()}
          </p>
        </div>
        <span className="text-3xl">💰</span>
      </div>

      {/* Per-route breakdown */}
      <div className="mt-2">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-1.5">
          Route Breakdown (after)
        </p>
        <div className="space-y-1">
          {after.route_metrics.map((rm) => (
            <div
              key={rm.route_id}
              className="flex items-center gap-2 rounded-md bg-gray-800 px-2.5 py-2"
            >
              <div
                className="h-2 w-2 rounded-full flex-shrink-0"
                style={{ background: rm.color }}
              />
              <span className="text-xs text-gray-300 flex-1 truncate">
                {rm.route_name}
              </span>
              <span
                className={`text-[11px] font-semibold ${
                  rm.load_factor >= 0.7
                    ? 'text-green-400'
                    : rm.load_factor >= 0.5
                      ? 'text-amber-400'
                      : 'text-red-400'
                }`}
              >
                {(rm.load_factor * 100).toFixed(0)}%
              </span>
              <span className="text-[11px] text-gray-500">
                {rm.estimated_riders}/{rm.bus_capacity}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
