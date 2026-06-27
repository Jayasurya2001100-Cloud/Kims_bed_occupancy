export interface ChartPackDateRange {
  start: string | null;
  end: string | null;
}

export interface ChartPackDailyRow {
  date: string;
  occupied_beds: number;
  total_beds: number;
  emergency_admissions: number;
  discharges: number;
  avg_los: number;
  patient_count: number;
  occupancy_rate: number;
  labour_staffing: number;
}

export interface ChartPackDepartmentLatest {
  department: string;
  occupied_beds: number;
  total_beds: number;
  occupancy_rate: number;
}

export interface ChartPackHeatmap {
  weekdays: string[];
  departments: string[];
  values: number[][];
}

export interface ChartPackScatterPoint {
  date: string;
  emergency_admissions: number;
  occupancy_rate: number;
  occupied_beds: number;
}

export interface ChartPackDiseaseSlice {
  category: string;
  patient_count: number;
}

export interface ChartPackDepartmentSeries {
  dates: string[];
  rates: number[];
  occupied: number[];
}

export interface ChartPack {
  date_range: ChartPackDateRange;
  daily: ChartPackDailyRow[];
  departments_latest: ChartPackDepartmentLatest[];
  heatmap: ChartPackHeatmap;
  scatter_pressure: ChartPackScatterPoint[];
  disease_mix: ChartPackDiseaseSlice[];
  department_series?: Record<string, ChartPackDepartmentSeries>;
}

/** Per-department forecast series from /api/analytics/department-forecasts */
export interface DeptForecastPoint {
  date: string;
  rate_pct: number;
  occupied: number;
  lower_pct: number;
  upper_pct: number;
  /** Model lower bound as bed count (same scale as `occupied`). */
  lower_beds: number;
  /** Model upper bound as bed count. */
  upper_beds: number;
}

export interface DepartmentForecastSeries {
  department: string;
  total_beds?: number;
  engine?: string;
  mape?: number;
  rmse?: number;
  model_name?: string;
  error?: string;
  points: DeptForecastPoint[];
}

export interface DepartmentForecastsPack {
  forecast_days: number;
  departments: DepartmentForecastSeries[];
}
