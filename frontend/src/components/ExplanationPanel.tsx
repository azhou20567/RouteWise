'use client'

import type { RouteRecommendation } from '@/types'

const ACTION_STYLES: Record<string, string> = {
  merge:        'bg-purple-900/60 text-purple-300',
  eliminate:    'bg-red-900/60 text-red-300',
  restructure:  'bg-blue-900/60 text-blue-300',
  adjust_timing:'bg-amber-900/60 text-amber-300',
}

interface Props {
  recommendation: RouteRecommendation
}

export default function ExplanationPanel({ recommendation: rec }: Props) {
  const confidencePct = Math.round(rec.confidence_score * 100)

  return (
    <section className="rounded-xl bg-gray-800 border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-gray-750 border-b border-gray-700 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">✨</span>
          <h3 className="text-sm font-semibold text-white">AI Analysis</h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-20 rounded-full bg-gray-700 overflow-hidden">
            <div
              className="h-full rounded-full bg-blue-500"
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-[11px] text-gray-400">{confidencePct}% confidence</span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Summary */}
        <p className="text-sm text-gray-300 leading-relaxed">
          {rec.analysis_summary}
        </p>

        {/* Inefficiencies */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-amber-500 mb-2">
            ⚠ Inefficiencies Found
          </p>
          <ul className="space-y-1.5">
            {rec.inefficiencies.map((item, i) => (
              <li key={i} className="flex gap-2 text-xs text-gray-400">
                <span className="text-amber-500 flex-shrink-0 mt-0.5">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Route edits */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-blue-400 mb-2">
            → Recommended Changes
          </p>
          <div className="space-y-2">
            {rec.route_edits.map((edit, i) => (
              <div
                key={i}
                className="rounded-lg bg-gray-900/60 border border-gray-700 p-3"
              >
                <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase tracking-wide ${
                      ACTION_STYLES[edit.action] ?? 'bg-gray-700 text-gray-300'
                    }`}
                  >
                    {edit.action}
                  </span>
                  {edit.affected_routes.map((r) => (
                    <span
                      key={r}
                      className="text-[10px] font-mono bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded"
                    >
                      {r}
                    </span>
                  ))}
                  {edit.estimated_distance_saving_km != null && (
                    <span className="text-[10px] text-green-400 ml-auto">
                      −{edit.estimated_distance_saving_km.toFixed(1)} km
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 leading-relaxed">
                  {edit.rationale}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Expected improvements table */}
        {rec.expected_improvements.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-green-500 mb-2">
              ↑ Expected Improvements
            </p>
            <div className="rounded-lg overflow-hidden border border-gray-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-900/50 text-gray-500">
                    <th className="text-left px-3 py-2 font-medium">Metric</th>
                    <th className="text-right px-3 py-2 font-medium">Before</th>
                    <th className="text-right px-3 py-2 font-medium">After</th>
                    <th className="text-right px-3 py-2 font-medium">Δ</th>
                  </tr>
                </thead>
                <tbody>
                  {rec.expected_improvements.map((imp, i) => (
                    <tr
                      key={i}
                      className="border-t border-gray-700/50 text-gray-300"
                    >
                      <td className="px-3 py-2">{imp.metric}</td>
                      <td className="px-3 py-2 text-right text-gray-500">
                        {imp.before_value} {imp.unit}
                      </td>
                      <td className="px-3 py-2 text-right font-semibold">
                        {imp.after_value} {imp.unit}
                      </td>
                      <td className="px-3 py-2 text-right text-green-400 font-semibold">
                        {imp.improvement_pct > 0 ? '+' : ''}
                        {imp.improvement_pct.toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Full explanation */}
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-gray-500 mb-2">
            Full Explanation
          </p>
          <p className="text-xs text-gray-400 leading-relaxed whitespace-pre-wrap">
            {rec.explanation}
          </p>
        </div>

        {/* Model attribution */}
        <p className="text-[10px] text-gray-600 border-t border-gray-700 pt-3">
          Generated by {rec.model_used}
        </p>
      </div>
    </section>
  )
}
