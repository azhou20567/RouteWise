'use client'

import type { Scenario } from '@/types'

interface Props {
  scenario: Scenario
  onChange: (s: Scenario) => void
  beforeLabel: string
  afterLabel: string
}

export default function ScenarioToggle({
  scenario,
  onChange,
  beforeLabel,
  afterLabel,
}: Props) {
  return (
    <div className="flex rounded-lg bg-gray-800 border border-gray-700 p-1 gap-1">
      <button
        onClick={() => onChange('before')}
        className={[
          'flex-1 rounded-md py-2 text-xs font-semibold transition-all duration-150',
          scenario === 'before'
            ? 'bg-gray-600 text-white shadow'
            : 'text-gray-400 hover:text-gray-200',
        ].join(' ')}
      >
        <span className="block text-[10px] font-normal text-gray-400 mb-0.5">
          Current
        </span>
        {beforeLabel}
      </button>
      <button
        onClick={() => onChange('after')}
        className={[
          'flex-1 rounded-md py-2 text-xs font-semibold transition-all duration-150',
          scenario === 'after'
            ? 'bg-green-700 text-white shadow'
            : 'text-gray-400 hover:text-gray-200',
        ].join(' ')}
      >
        <span className="block text-[10px] font-normal text-gray-400 mb-0.5">
          Optimized
        </span>
        {afterLabel}
      </button>
    </div>
  )
}
