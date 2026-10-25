/**
 * Typed API client for the Wind Forecast Monitoring backend.
 * Reads base URL from import.meta.env.VITE_API_URL or defaults to empty string
 * (allowing Vite dev proxy to route to http://127.0.0.1:8001).
 */

import {
  AccuracyResponse,
  ForecastResponse,
  HorizonResponse,
  MetaResponse,
} from './types';

const API_BASE = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        errorDetail = data.detail;
      }
    } catch {
      // Ignore JSON parse error on non-JSON response
    }
    throw new Error(errorDetail);
  }
  return res.json();
}

export async function fetchMeta(): Promise<MetaResponse> {
  const res = await fetch(`${API_BASE}/api/meta`);
  return handleResponse<MetaResponse>(res);
}

export async function fetchForecast(targetDate: string): Promise<ForecastResponse> {
  const url = `${API_BASE}/api/forecast?target_date=${encodeURIComponent(targetDate)}`;
  const res = await fetch(url);
  return handleResponse<ForecastResponse>(res);
}

export async function fetchAccuracy(start: string, end: string): Promise<AccuracyResponse> {
  const url = `${API_BASE}/api/accuracy?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
  const res = await fetch(url);
  return handleResponse<AccuracyResponse>(res);
}

export async function fetchHorizon(start: string, end: string): Promise<HorizonResponse> {
  const url = `${API_BASE}/api/accuracy/horizon?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
  const res = await fetch(url);
  return handleResponse<HorizonResponse>(res);
}
