export interface RouteStop {
  stop_id: string
  sequence: number
  arrival_offset_minutes: number
}

export interface Route {
  route_id: string
  name: string
  color: string
  bus_capacity: number
  departure_time: string
  stops: RouteStop[]
  total_distance_km: number
  total_duration_minutes: number
  avg_load_factor: number
  merged_from: string[] | null
}

export interface Stop {
  stop_id: string
  name: string
  lat: number
  lng: number
  zone_id: string
  estimated_riders: number
}

export interface Zone {
  zone_id: string
  name: string
  polygon: number[][]
  school_level: string
  peak_demand_multiplier: number
}

export interface OptimizedScenario {
  routes: Route[]
  eliminated_routes: string[]
  total_distance_km: number
  total_duration_minutes: number
}

export interface Dataset {
  dataset_id: string
  name: string
  school_name: string
  school_level: string
  school_lat: number
  school_lng: number
  stops: Stop[]
  zones: Zone[]
  routes: Route[]
  optimized_scenario: OptimizedScenario
}

export interface DatasetMeta {
  dataset_id: string
  name: string
  school_name: string
  school_level: string
  school_lat: number
  school_lng: number
  num_routes_before: number
  num_routes_after: number
  total_stops: number
}

export interface RouteMetric {
  route_id: string
  route_name: string
  color: string
  num_stops: number
  bus_capacity: number
  estimated_riders: number
  load_factor: number
  total_distance_km: number
  total_duration_minutes: number
  cost_usd: number
  co2_kg: number
}

export interface ScenarioMetrics {
  scenario: 'before' | 'after'
  dataset_id: string
  num_routes: number
  total_distance_km: number
  total_duration_minutes: number
  total_riders: number
  avg_load_factor: number
  total_cost_usd: number
  total_co2_kg: number
  route_metrics: RouteMetric[]
}

export interface MetricsDelta {
  routes_eliminated: number
  distance_saved_km: number
  distance_saved_pct: number
  duration_saved_minutes: number
  cost_saved_usd_daily: number
  cost_saved_pct: number
  co2_saved_kg_daily: number
  load_factor_improvement: number
  estimated_annual_savings_usd: number
}

export interface MetricsResponse {
  before: ScenarioMetrics
  after: ScenarioMetrics
  delta: MetricsDelta
}

export type RouteAction = 'merge' | 'eliminate' | 'restructure' | 'adjust_timing'

export interface RouteEdit {
  action: RouteAction
  affected_routes: string[]
  rationale: string
  estimated_distance_saving_km?: number
}

export interface ExpectedImprovement {
  metric: string
  before_value: number
  after_value: number
  unit: string
  improvement_pct: number
}

export interface RouteRecommendation {
  dataset_id: string
  analysis_summary: string
  inefficiencies: string[]
  route_edits: RouteEdit[]
  expected_improvements: ExpectedImprovement[]
  explanation: string
  confidence_score: number
  model_used: string
}

export interface AnalysisResponse {
  recommendation: RouteRecommendation
  before: ScenarioMetrics
  after: ScenarioMetrics
  delta: MetricsDelta
}

export type Scenario = 'before' | 'after'
