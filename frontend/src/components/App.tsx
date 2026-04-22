'use client'

import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type {
  AnalysisResponse,
  Dataset,
  DatasetMeta,
  MetricsResponse,
  Scenario,
} from '@/types'
import DatasetSelector from './DatasetSelector'
import ExplanationPanel from './ExplanationPanel'
import GoogleMapView from './GoogleMapView'
import MetricsPanel from './MetricsPanel'
import ScenarioToggle from './ScenarioToggle'

export default function App() {
  const [datasetList, setDatasetList] = useState<DatasetMeta[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null)
  const [scenario, setScenario] = useState<Scenario>('before')
  const [loadingDataset, setLoadingDataset] = useState(false)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Load dataset list on mount
  useEffect(() => {
    api
      .listDatasets()
      .then(setDatasetList)
      .catch((e) => setError(e.message))
  }, [])

  const handleSelectDataset = async (id: string) => {
    if (id === selectedId) return
    setSelectedId(id)
    setDataset(null)
    setMetrics(null)
    setAnalysis(null)
    setScenario('before')
    setError(null)
    setLoadingDataset(true)

    try {
      const [ds, m] = await Promise.all([api.getDataset(id), api.getMetrics(id)])
      setDataset(ds)
      setMetrics(m)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load dataset')
    } finally {
      setLoadingDataset(false)
    }
  }

  const handleRunAnalysis = async () => {
    if (!selectedId) return
    setLoadingAnalysis(true)
    setError(null)

    try {
      const result = await api.recommend(selectedId)
      setAnalysis(result)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed')
    } finally {
      setLoadingAnalysis(false)
    }
  }

  const activeRoutes =
    dataset
      ? scenario === 'before'
        ? dataset.routes
        : dataset.optimized_scenario.routes
      : []

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-gray-950 text-white">
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header className="flex h-14 flex-shrink-0 items-center justify-between border-b border-gray-800 bg-gray-900 px-6">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold tracking-tight">🚌 RouteWise</span>
          <span className="hidden sm:block text-sm text-gray-500">
            School Bus Route Optimizer
          </span>
        </div>
        {dataset && (
          <span className="text-xs text-gray-500">
            {dataset.school_name} · {dataset.school_level}
          </span>
        )}
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Body                                                                 */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar */}
        <aside className="w-[400px] flex-shrink-0 overflow-y-auto border-r border-gray-800 bg-gray-900 flex flex-col gap-4 p-4 pb-8">
          {/* Dataset selector */}
          <DatasetSelector
            datasets={datasetList}
            selectedId={selectedId}
            onSelect={handleSelectDataset}
            loading={loadingDataset}
          />

          {/* Loading spinner */}
          {loadingDataset && (
            <div className="flex items-center justify-center py-6">
              <div className="h-6 w-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div className="rounded-lg border border-red-700 bg-red-900/40 p-3 text-sm text-red-300">
              {error}
            </div>
          )}

          {dataset && metrics && (
            <>
              {/* Scenario toggle */}
              <ScenarioToggle
                scenario={scenario}
                onChange={setScenario}
                beforeLabel={`${dataset.routes.length} routes`}
                afterLabel={`${dataset.optimized_scenario.routes.length} routes`}
              />

              {/* Metrics */}
              <MetricsPanel
                before={metrics.before}
                after={metrics.after}
                delta={metrics.delta}
                scenario={scenario}
              />

              {/* Run AI Analysis */}
              {!analysis && (
                <button
                  onClick={handleRunAnalysis}
                  disabled={loadingAnalysis}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-blue-600 bg-blue-600/20 py-3 text-sm font-semibold text-blue-300 transition-all hover:bg-blue-600/30 disabled:cursor-wait disabled:opacity-60"
                >
                  {loadingAnalysis ? (
                    <>
                      <div className="h-4 w-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
                      Generating AI Analysis…
                    </>
                  ) : (
                    <>✨ Generate AI Analysis</>
                  )}
                </button>
              )}

              {/* Explanation panel */}
              {analysis && (
                <ExplanationPanel recommendation={analysis.recommendation} />
              )}
            </>
          )}
        </aside>

        {/* Map area */}
        <main className="relative flex-1 overflow-hidden">
          {dataset ? (
            <GoogleMapView dataset={dataset} activeRoutes={activeRoutes} />
          ) : (
            <div className="flex h-full items-center justify-center bg-gray-900">
              <div className="text-center">
                <p className="text-5xl mb-4">🗺️</p>
                <p className="text-lg font-semibold text-gray-400">
                  Select a dataset to begin
                </p>
                <p className="mt-1 text-sm text-gray-600">
                  Choose a school from the panel on the left
                </p>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
