import React, { useEffect, useState } from 'react';
import { fetchForecast, fetchMeta } from '../api';
import { ForecastResponse, MetaResponse } from '../types';
import { CutoffBanner } from '../components/CutoffBanner';
import { ForecastChart } from '../components/ForecastChart';

const fmtMW = (v: number) => Math.round(v).toLocaleString('en-GB');
const fmtSigned = (v: number) => `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('en-GB')}`;
const fmtDT = (iso: string) => iso.replace('T', ' ').slice(0, 16);

export const ForecastPage: React.FC = () => {
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('2026-01-15');
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isLedgerOpen, setIsLedgerOpen] = useState<boolean>(false);
  const closeRef = React.useRef<HTMLButtonElement>(null);

  // Dialog behavior: Escape closes, page scroll locks, close button gets focus
  useEffect(() => {
    if (!isLedgerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsLedgerOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [isLedgerOpen]);

  // Load metadata on mount
  useEffect(() => {
    let mounted = true;
    fetchMeta()
      .then((data) => {
        if (!mounted) return;
        setMeta(data);
        if (data.available_target_days.length > 0) {
          if (data.available_target_days.includes('2026-01-15')) {
            setSelectedDate('2026-01-15');
          } else {
            setSelectedDate(data.available_target_days[0]);
          }
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

  // Fetch forecast whenever selectedDate changes
  useEffect(() => {
    if (!selectedDate) return;

    let mounted = true;
    setIsLoading(true);
    setError(null);

    fetchForecast(selectedDate)
      .then((data) => {
        if (!mounted) return;
        setForecastData(data);
        setIsLoading(false);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to fetch forecast');
        setIsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedDate]);

  const handleRetry = () => {
    if (selectedDate) {
      setIsLoading(true);
      setError(null);
      fetchForecast(selectedDate)
        .then((data) => {
          setForecastData(data);
          setIsLoading(false);
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : 'Failed to fetch forecast');
          setIsLoading(false);
        });
    }
  };

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.value) {
      setSelectedDate(e.target.value);
    }
  };

  // Compute summary stats
  const slots = forecastData?.slots || [];
  const forecasts = slots.map((s) => s.forecast_mw);
  const actuals = slots.filter((s) => s.actual_mw !== null).map((s) => s.actual_mw as number);

  const peakForecast = forecasts.length ? Math.max(...forecasts) : 0;
  const minForecast = forecasts.length ? Math.min(...forecasts) : 0;
  const avgForecast = forecasts.length ? forecasts.reduce((a, b) => a + b, 0) / forecasts.length : 0;
  const avgActual = actuals.length ? actuals.reduce((a, b) => a + b, 0) / actuals.length : null;

  const cutoffSample = slots.length > 0 ? slots[0].cutoff : null;

  const minDate = meta?.available_target_start || '2026-01-02';
  const maxDate = meta?.available_target_end || '2026-02-01';

  return (
    <div className="forecast-page">
      {/* Page header + target-day picker */}
      <div className="view-head">
        <div className="view-title">
          <h1>Day-ahead wind forecast</h1>
          <p className="view-note">
            National wind generation locked at the D-1 09:00 UTC auction gate — the last forecast
            the desk could act on.
          </p>
        </div>

        <div className="date-field">
          <label className="date-label" htmlFor="target-date-picker">
            Target day
          </label>
          <input
            id="target-date-picker"
            type="date"
            className="date-input tabular-nums"
            min={minDate}
            max={maxDate}
            value={selectedDate}
            onChange={handleDateChange}
            disabled={isLoading}
            aria-label="Select target delivery day"
          />
        </div>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="state-panel" role="status" aria-live="polite">
          <div className="spinner" aria-hidden="true" />
          <p className="state-note">Loading forecast and outturn for {selectedDate}</p>
        </div>
      )}

      {/* Error state */}
      {!isLoading && error && (
        <div className="state-panel" role="alert">
          <p className="state-title is-error">Data unavailable</p>
          <p className="state-note">{error}</p>
          <button type="button" className="btn-text" onClick={handleRetry}>
            Retry request
          </button>
        </div>
      )}

      {/* Desk layout: decision ledger left, chart + slots right */}
      {!isLoading && !error && forecastData && (
        <div className="desk-grid is-forecast">
          <aside className="desk-side">
            <CutoffBanner
              cutoffTime={cutoffSample}
              earliestPublish={forecastData.earliest_publish_time}
              latestPublish={forecastData.latest_publish_time}
              cutoffHourUtc={forecastData.cutoff_hour_utc}
              targetDate={selectedDate}
            />

            <div className="stat-rail is-column">
              <div className="stat">
                <div className="stat-label">Peak forecast</div>
                <div className="stat-value tabular-nums">
                  {fmtMW(peakForecast)}
                  <span className="stat-unit">MW</span>
                </div>
                <div className="stat-sub">Highest hourly expectation</div>
              </div>

              <div className="stat">
                <div className="stat-label">Base forecast</div>
                <div className="stat-value tabular-nums">
                  {fmtMW(minForecast)}
                  <span className="stat-unit">MW</span>
                </div>
                <div className="stat-sub">Lowest hourly expectation</div>
              </div>

              <div className="stat">
                <div className="stat-label">Daily mean forecast</div>
                <div className="stat-value tabular-nums">
                  {fmtMW(avgForecast)}
                  <span className="stat-unit">MW</span>
                </div>
                <div className="stat-sub">Across all slots</div>
              </div>

              {avgActual !== null && (
                <div className="stat" style={{ '--accent': 'var(--act)' } as React.CSSProperties}>
                  <div className="stat-label">Daily mean outturn</div>
                  <div className="stat-value tabular-nums" style={{ color: 'var(--act)' }}>
                    {fmtMW(avgActual)}
                    <span className="stat-unit">MW</span>
                  </div>
                  <div className="stat-sub">Actual generation, all slots</div>
                </div>
              )}
            </div>
          </aside>

          <section className="desk-main">
            <ForecastChart slots={forecastData.slots} targetDate={selectedDate} />

            {/* Ledger trigger — opens the scrollable dialog */}
            <div className="panel">
              <button
                type="button"
                className="collapse-toggle"
                onClick={() => setIsLedgerOpen(true)}
                aria-haspopup="dialog"
              >
                <span>Slot ledger · {forecastData.slots.length} hourly slots</span>
                <span className="chev" aria-hidden="true">
                  &nbsp;+
                </span>
              </button>
            </div>
          </section>
        </div>
      )}

      {/* Slot ledger dialog */}
      {!isLoading && !error && forecastData && isLedgerOpen && (
        <div
          className="modal-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsLedgerOpen(false);
          }}
        >
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ledger-dialog-title"
          >
            <div className="modal-head">
              <h2 className="panel-kicker" id="ledger-dialog-title">
                Slot ledger · {selectedDate}
              </h2>
              <span className="chart-note">Errors in MW · all times UTC</span>
              <button
                ref={closeRef}
                type="button"
                className="btn-text"
                onClick={() => setIsLedgerOpen(false)}
              >
                Close
              </button>
            </div>

            <div className="modal-body table-scroll">
              <table className="slot-table tabular-nums">
                <thead>
                  <tr>
                    <th>Slot (UTC)</th>
                    <th className="ta-r">Forecast MW</th>
                    <th>Published (UTC)</th>
                    <th>Cutoff</th>
                    <th className="ta-r">Actual MW</th>
                    <th className="ta-r">Error MW</th>
                  </tr>
                </thead>
                <tbody>
                  {forecastData.slots.map((slot) => {
                    const errorVal =
                      slot.actual_mw !== null ? slot.forecast_mw - slot.actual_mw : null;
                    return (
                      <tr key={slot.startTime}>
                        <td className="num">{slot.startTime.substring(11, 16)}</td>
                        <td className="num ta-r">{fmtMW(slot.forecast_mw)}</td>
                        <td className="num dim">{fmtDT(slot.publishTime)}</td>
                        <td className="num dim">{slot.cutoff.substring(11, 16)}</td>
                        <td className="num ta-r">
                          {slot.actual_mw !== null ? fmtMW(slot.actual_mw) : '—'}
                        </td>
                        <td className="num ta-r">
                          {errorVal !== null ? (
                            <span className={errorVal > 0 ? 'delta-pos' : 'delta-neg'}>
                              {fmtSigned(errorVal)}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
