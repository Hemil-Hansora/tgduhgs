import React, { useEffect, useState } from 'react';
import { fetchAccuracy, fetchHorizon, fetchMeta } from '../api';
import { AccuracyResponse, HorizonBucket, MetaResponse } from '../types';
import { MetricCard } from '../components/MetricCard';
import { AccuracyCharts } from '../components/AccuracyCharts';

const PRESETS: Array<{ label: string; start: string; end: string }> = [
  { label: 'Full window', start: '2026-01-02', end: '2026-02-01' },
  { label: 'Week 1', start: '2026-01-02', end: '2026-01-09' },
  { label: 'Week 2', start: '2026-01-09', end: '2026-01-16' },
  { label: 'Week 3', start: '2026-01-16', end: '2026-01-23' },
  { label: 'Week 4', start: '2026-01-23', end: '2026-01-30' },
];

export const AccuracyPage: React.FC = () => {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [startDate, setStartDate] = useState<string>('2026-01-02');
  const [endDate, setEndDate] = useState<string>('2026-02-01');

  const [accuracyData, setAccuracyData] = useState<AccuracyResponse | null>(null);
  const [horizonBuckets, setHorizonBuckets] = useState<HorizonBucket[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Load available dates
  useEffect(() => {
    let mounted = true;
    fetchMeta()
      .then((data) => {
        if (!mounted) return;
        setMeta(data);
        if (data.available_target_start && data.available_target_end) {
          setStartDate(data.available_target_start);
          setEndDate(data.available_target_end);
        }
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to connect to backend API');
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  // Fetch accuracy & horizon metrics when dates change
  useEffect(() => {
    if (!startDate || !endDate) return;
    if (startDate >= endDate) {
      setError('Start date must be strictly before end date.');
      return;
    }

    let mounted = true;
    setIsLoading(true);
    setError(null);

    Promise.all([fetchAccuracy(startDate, endDate), fetchHorizon(startDate, endDate)])
      .then(([accRes, horRes]) => {
        if (!mounted) return;
        setAccuracyData(accRes);
        setHorizonBuckets(horRes.buckets);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to calculate accuracy metrics');
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [startDate, endDate]);

  const handleRetry = () => {
    if (startDate && endDate) {
      setIsLoading(true);
      setError(null);
      Promise.all([fetchAccuracy(startDate, endDate), fetchHorizon(startDate, endDate)])
        .then(([accRes, horRes]) => {
          setAccuracyData(accRes);
          setHorizonBuckets(horRes.buckets);
          setIsLoading(false);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Failed to calculate accuracy metrics');
          setIsLoading(false);
        });
    }
  };

  const setPreset = (start: string, end: string) => {
    setStartDate(start);
    setEndDate(end);
  };

  const minDate = meta?.available_target_start || '2026-01-02';
  const maxDate = meta?.available_target_end || '2026-02-01';
  const metrics = accuracyData?.metrics;

  return (
    <div className="accuracy-page">
      {/* Page header + range controls */}
      <div className="view-head">
        <div className="view-title">
          <h1>Forecast accuracy &amp; buffer</h1>
          <p className="view-note">
            Day-ahead forecast error against actual outturn — the number to size the safety buffer
            around.
          </p>
        </div>

        <div className="controls-col">
          <div className="date-field">
            <label className="date-label" htmlFor="accuracy-start-date">
              Range
            </label>
            <input
              id="accuracy-start-date"
              type="date"
              className="date-input tabular-nums"
              min={minDate}
              max={maxDate}
              value={startDate}
              onChange={(e) => e.target.value && setStartDate(e.target.value)}
              disabled={isLoading}
              aria-label="Start target date"
            />
            <span className="date-sep" aria-hidden="true">
              →
            </span>
            <input
              id="accuracy-end-date"
              type="date"
              className="date-input tabular-nums"
              min={minDate}
              max={maxDate}
              value={endDate}
              onChange={(e) => e.target.value && setEndDate(e.target.value)}
              disabled={isLoading}
              aria-label="End target date"
            />
          </div>

          {/* Quick presets */}
          <div className="range-presets">
            <span className="presets-label">Presets</span>
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                className={`preset-btn ${
                  startDate === p.start && endDate === p.end ? 'is-active' : ''
                }`}
                onClick={() => setPreset(p.start, p.end)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="state-panel" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="state-note">
            Computing accuracy metrics for {startDate} → {endDate}
          </p>
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div className="state-panel" role="alert">
          <p className="state-title is-error">Accuracy evaluation failed</p>
          <p className="state-note">{error}</p>
          <button type="button" className="btn-text" onClick={handleRetry}>
            Retry request
          </button>
        </div>
      )}

      {/* Metric ledger + charts */}
      {!isLoading && !error && metrics && accuracyData && (
        <>
          <div className="stat-rail">
            <MetricCard
              title="MAE"
              value={metrics.mae_mw}
              unit="MW"
              tooltip="Mean Absolute Error — average magnitude of hourly errors, regardless of direction."
              subtitle="Avg error magnitude"
            />

            <MetricCard
              title="RMSE"
              value={metrics.rmse_mw}
              unit="MW"
              tooltip="Root Mean Squared Error — severely penalizes large forecast misses; key for tail risk."
              subtitle="Large-miss penalty"
            />

            <MetricCard
              title="Bias (Mean Error)"
              value={
                metrics.bias_mw > 0
                  ? `+${Math.round(metrics.bias_mw).toLocaleString('en-GB')}`
                  : Math.round(metrics.bias_mw).toLocaleString('en-GB')
              }
              unit="MW"
              valueColor={metrics.bias_mw > 0 ? 'var(--danger)' : 'var(--good)'}
              tooltip="Forecast minus actual. Positive means over-forecasting — the buyer risks under-buying in the auction."
              subtitle={metrics.bias_mw > 0 ? 'Over-forecasting' : 'Under-forecasting'}
            />

            <MetricCard
              title="P90 abs error"
              value={metrics.p90_abs_error_mw}
              unit="MW"
              tooltip="90th percentile of absolute error: 90% of hours had an error smaller than this value."
              subtitle="90% confidence"
            />

            <MetricCard
              title="MAE % of actual"
              value={`${metrics.mae_pct_of_mean_actual.toFixed(1)}%`}
              tooltip="MAE divided by mean actual wind generation; avoids division by zero from per-slot MAPE."
              subtitle="Relative error"
            />

            <MetricCard
              title="Safety buffer"
              value={metrics.buffer_mw}
              unit="MW"
              valueColor="var(--brass)"
              tooltip="90th percentile of positive errors: recommended backup procurement to cover 90% of over-forecasts."
              subtitle="Plan backup MW"
            />
          </div>

          {/* Slot coverage footnote */}
          <div className="footnote-row">
            <span>
              {metrics.total_slots - metrics.dropped_slots} of {metrics.total_slots} hourly slots
              evaluated · {startDate} → {endDate}
            </span>
            <span className={metrics.dropped_slots > 0 ? 'footnote-warn' : undefined}>
              Dropped slots: {metrics.dropped_slots}
            </span>
          </div>

          <AccuracyCharts series={accuracyData.series} horizonBuckets={horizonBuckets} />
        </>
      )}
    </div>
  );
};
