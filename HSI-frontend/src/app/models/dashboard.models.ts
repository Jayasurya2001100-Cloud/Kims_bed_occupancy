export interface OccupancyData {
  date: string;
  occupied_beds: number;
  total_beds: number;
  occupancy_rate: number;
  department: string;
  icu_beds: number;
  emergency_admissions: number;
  discharges: number;
}

export interface ForecastRequest {
  days?: number;
  department?: string;
  model_preference?: string | null;
  as_of_date?: string | null;
}

export interface CopilotChatRequest {
  query: string;
  as_of_date?: string | null;
  model_preference?: string | null;
  forecast_days?: number;
}

export interface CopilotChatResponse {
  answer: string;
  as_of_date: string;
  model_preference?: string | null;
  forecast_days: number;
  grounded: boolean;
}

export const DEFAULT_FORECAST_DAYS = 14;
export const MAX_FORECAST_DAYS = 30;

export interface GenericForecastDataPoint {
  date: string;
  predicted_value: number;
  lower_bound?: number;
  upper_bound?: number;
}

export interface GenericForecastResponse {
  forecast_data: GenericForecastDataPoint[];
  confidence_interval: {
    lower: number[];
    upper: number[];
  };
  model_metrics: {
    mape: number;
    rmse: number;
    trend?: number;
    backtest_days?: number;
    engine?: string;
    week1_mape?: number;
    week2_mape?: number;
    week3_mape?: number;
    iterations_completed?: number;
  };
  forecast_model: {
    name: string;
    summary: string;
    confidence_intervals: string;
    accuracy_note: string;
    explanation?: string;
    insights?: string[];
  };
  week1_predictions?: GenericForecastDataPoint[];
  week2_predictions?: GenericForecastDataPoint[];
  week3_predictions?: GenericForecastDataPoint[];
}

export interface ForecastData {
  date: string;
  predicted_occupancy_rate: number;
  predicted_occupied_beds: number;
  lower_bound: number;
  upper_bound: number;
}

export interface ForecastResponse {
  forecast_data: ForecastData[];
  confidence_interval: {
    lower: number[];
    upper: number[];
  };
  model_metrics: {
    mape: number;
    rmse: number;
    trend?: number;
    /** Tail holdout length (or 0 if unavailable) */
    backtest_days?: number;
    engine?: string;
  };
  forecast_model: {
    name: string;
    summary: string;
    confidence_intervals: string;
    accuracy_note: string;
    explanation?: string;
    insights?: string[];
  };
}

export interface AlertData {
  alert_type: string;
  message: string;
  severity: string;
  timestamp: string;
  department?: string;
}

export interface DashboardMetrics {
  current_occupancy_rate: number;
  occupied_beds: number;
  available_beds: number;
  total_beds: number;
  icu_occupancy_rate: number;
  icu_occupied_beds: number;
  icu_available_beds: number;
  icu_total_beds: number;
  predicted_occupancy_7_days: number;
  emergency_admissions_today: number;
  avg_length_of_stay: number;
  /** YYYY-MM-DD: latest day in the dataset used for snapshot tiles (not the forecast horizon). */
  data_as_of_date: string;
  alerts: AlertData[];
}

export interface Department {
  name: string;
  total_beds: number;
  occupied_beds: number;
  occupancy_rate: number;
}
