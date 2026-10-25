export interface MetaResponse {
  cutoff_rule: string;
  cutoff_hour_utc: number;
  available_target_start: string | null;
  available_target_end: string | null;
  available_target_days: string[];
  total_actual_slots: number;
  total_forecast_rows: number;
  dropped_slot_count: number;
}

export interface ForecastSlot {
  startTime: string;
  forecast_mw: number;
  publishTime: string;
  cutoff: string;
  actual_mw: number | null;
}

export interface ForecastResponse {
  target_date: string;
  cutoff_hour_utc: number;
  earliest_publish_time: string | null;
  latest_publish_time: string | null;
  slots_count: number;
  slots: ForecastSlot[];
}

export interface AccuracyMetrics {
  mae_mw: number;
  rmse_mw: number;
  bias_mw: number;
  p50_abs_error_mw: number;
  p90_abs_error_mw: number;
  p95_abs_error_mw: number;
  mae_pct_of_mean_actual: number;
  buffer_mw: number;
  total_slots: number;
  dropped_slots: number;
}

export interface AccuracySlot {
  startTime: string;
  forecast_mw: number;
  actual_mw: number;
  error_mw: number;
}

export interface AccuracyResponse {
  start: string;
  end: string;
  metrics: AccuracyMetrics;
  series: AccuracySlot[];
}

export interface HorizonBucket {
  bucket: string;
  mae_mw: number;
  bias_mw: number;
  count: number;
}

export interface HorizonResponse {
  start: string;
  end: string;
  buckets: HorizonBucket[];
}
