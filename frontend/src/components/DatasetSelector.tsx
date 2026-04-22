'use client'

import type { DatasetMeta } from '@/types'

interface Props {
  datasets: DatasetMeta[]
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
}

const LEVEL_LABEL: Record<string, string> = {
  elementary: 'Elementary',
  middle: 'Middle School',
  high: 'High School',
}

export default function DatasetSelector({
  datasets,
  selectedId,
  onSelect,
  loading,
}: Props) {
  return (
    <section>
      <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-500 mb-2">
        Demo Dataset
      </h2>
      <div className="grid grid-cols-2 gap-2">
        {datasets.length === 0 ? (
          <p className="col-span-2 text-xs text-gray-600 py-2">
            Loading datasets…
          </p>
        ) : (
          datasets.map((ds) => {
            const isSelected = ds.dataset_id === selectedId
            return (
              <button
                key={ds.dataset_id}
                onClick={() => onSelect(ds.dataset_id)}
                disabled={loading}
                className={[
                  'text-left rounded-xl border p-3 transition-all duration-150',
                  isSelected
                    ? 'border-blue-500 bg-blue-600/20 ring-1 ring-blue-500'
                    : 'border-gray-700 bg-gray-800 hover:border-gray-500 hover:bg-gray-750',
                  loading ? 'cursor-wait opacity-60' : 'cursor-pointer',
                ].join(' ')}
              >
                <p
                  className={`text-sm font-semibold leading-tight ${isSelected ? 'text-white' : 'text-gray-200'}`}
                >
                  {ds.school_name}
                </p>
                <p className="text-[11px] text-gray-400 mt-0.5">
                  {LEVEL_LABEL[ds.school_level] ?? ds.school_level}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[10px] bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                    {ds.num_routes_before} → {ds.num_routes_after} routes
                  </span>
                  <span className="text-[10px] text-gray-500">
                    {ds.total_stops} stops
                  </span>
                </div>
              </button>
            )
          })
        )}
      </div>
    </section>
  )
}
