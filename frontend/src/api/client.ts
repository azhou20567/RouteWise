import type {
  AnalysisResponse,
  Dataset,
  DatasetMeta,
  MetricsResponse,
} from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: 'no-store' })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

async function post<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status} ${text}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  listDatasets: () => get<DatasetMeta[]>('/datasets'),
  getDataset: (id: string) => get<Dataset>(`/datasets/${id}`),
  getMetrics: (id: string) => get<MetricsResponse>(`/analysis/${id}/metrics`),
  recommend: (id: string) => post<AnalysisResponse>(`/analysis/${id}/recommend`),
}
