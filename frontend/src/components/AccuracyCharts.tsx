import React, { useState } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';
import { AccuracySlot, HorizonBucket } from '../types';

interface AccuracyChartsProps {
  series: AccuracySlot[];
  horizonBuckets: HorizonBucket[];
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: Array<{
    value: number;
    name: string;
    color: string;
    dataKey: string;
  }>;
  label?: string;
}

const SeriesTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  const fcst = payload.find((p) => p.dataKey === 'forecast_mw')?.value;
  const act = payload.find((p) => p.dataKey === 'actual_mw')?.value;
  const diff = typeof fcst === 'number' && typeof act === 'number' ? fcst - act : null;

  return (
    <div className="tooltip-panel" role="tooltip">
      <div className="tooltip-kicker tabular-nums">{label} UTC</div>
      {typeof fcst === 'number' && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--fc)' }} />
            Forecast
          </span>
          <span className="tooltip-val tabular-nums">{Math.round(fcst).toLocaleString('en-GB')} MW</span>
        </div>
      )}
      {typeof act === 'number' && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--act)' }} />
            Actual
          </span>
          <span className="tooltip-val tabular-nums">{Math.round(act).toLocaleString('en-GB')} MW</span>
        </div>
      )}
      {diff !== null && (
        <div className="tooltip-diff">
          <span>Error (Fcst − Act)</span>
          <span className={`diff-tag tabular-nums ${diff > 0 ? 'over' : 'under'}`}>
            {diff > 0 ? '+' : ''}
            {Math.round(diff).toLocaleString('en-GB')} MW
          </span>
        </div>
      )}
    </div>
  );
};

const ErrorTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const err = payload[0]?.value;

  return (
    <div className="tooltip-panel" role="tooltip">
      <div className="tooltip-kicker tabular-nums">{label} UTC</div>
      <div className="tooltip-row">
        <span>Hourly error</span>
        <span
          className={`tooltip-val tabular-nums ${typeof err === 'number' && err > 0 ? 'over' : 'under'}`}
          style={{ color: typeof err === 'number' && err > 0 ? 'var(--danger)' : 'var(--good)' }}
        >
          {(typeof err === 'number' && err > 0 ? '+' : '') + Math.round(err || 0)} MW
        </span>
      </div>
      <div className="tooltip-note">
        {typeof err === 'number' && err > 0
          ? 'Over-forecast — the utility under-buys in the auction.'
          : 'Under-forecast — the utility over-buys in the auction.'}
      </div>
    </div>
  );
};

const HorizonTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;
  const mae = payload.find((p) => p.dataKey === 'mae_mw')?.value;
  const bias = payload.find((p) => p.dataKey === 'bias_mw')?.value;

  return (
    <div className="tooltip-panel" role="tooltip">
      <div className="tooltip-kicker">{label} hrs lead time</div>
      {typeof mae === 'number' && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--fc)' }} />
            MAE
          </span>
          <span className="tooltip-val tabular-nums">{Math.round(mae).toLocaleString('en-GB')} MW</span>
        </div>
      )}
      {typeof bias === 'number' && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--brass)' }} />
            Bias
          </span>
          <span
            className="tooltip-val tabular-nums"
            style={{ color: bias > 0 ? 'var(--danger)' : 'var(--good)' }}
          >
            {bias > 0 ? '+' : ''}
            {Math.round(bias)} MW
          </span>
        </div>
      )}
    </div>
  );
};

export const AccuracyCharts: React.FC<AccuracyChartsProps> = ({
  series,
  horizonBuckets,
}) => {
  const [activeView, setActiveView] = useState<'line' | 'error' | 'horizon' | 'all'>('line');

  const lineData = series.map((s) => ({
    time: s.startTime.substring(5, 16).replace('T', ' '),
    forecast_mw: s.forecast_mw,
    actual_mw: s.actual_mw,
    error_mw: s.error_mw,
  }));

  const renderLineChart = (height = 360) => (
    <div className="panel">
      <div className="panel-head">
        <h2 className="chart-title">Forecast vs actual generation</h2>
        <div className="legend">
          <div className="legend-item">
            <span className="legend-line forecast" />
            <span>Day-ahead forecast (MW)</span>
          </div>
          <div className="legend-item">
            <span className="legend-line actual" />
            <span>Actual outturn (MW)</span>
          </div>
        </div>
      </div>
      <div className="chart-body">
        <div className="chart-wrapper" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={lineData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
              <CartesianGrid stroke="var(--rule)" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="var(--text-dim)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                interval="preserveStartEnd"
                dy={8}
              />
              <YAxis
                stroke="var(--text-dim)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                tickFormatter={(v) => `${(v / 1000).toFixed(1)}k`}
                width={56}
              />
              <Tooltip content={<SeriesTooltip />} />
              <Line
                type="monotone"
                dataKey="forecast_mw"
                name="Forecast"
                stroke="var(--fc)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="actual_mw"
                name="Actual"
                stroke="var(--act)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  const renderErrorChart = (height = 360) => (
    <div className="panel">
      <div className="panel-head">
        <h2 className="chart-title">Hourly forecast error</h2>
        <span className="chart-note">&gt;0 = over-forecast · &lt;0 = under-forecast</span>
      </div>
      <div className="chart-body">
        <div className="chart-wrapper" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={lineData} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
              <CartesianGrid stroke="var(--rule)" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="var(--text-dim)"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                interval="preserveStartEnd"
                dy={8}
              />
              <YAxis
                stroke="var(--text-dim)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                tickFormatter={(v) => `${Math.round(v)}`}
                width={56}
              />
              <ReferenceLine y={0} stroke="var(--hairline-strong)" />
              <Tooltip content={<ErrorTooltip />} />
              <Bar dataKey="error_mw" name="Error" isAnimationActive={false}>
                {lineData.map((entry, index) => (
                  <Cell
                    key={index}
                    fill={entry.error_mw > 0 ? 'var(--danger)' : 'var(--good)'}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  const renderHorizonChart = (height = 360) => (
    <div className="panel">
      <div className="panel-head">
        <h2 className="chart-title">Error by forecast lead time</h2>
        <div className="legend">
          <div className="legend-item">
            <span className="dot" style={{ backgroundColor: 'var(--fc)' }} />
            <span>MAE (MW)</span>
          </div>
          <div className="legend-item">
            <span className="dot" style={{ backgroundColor: 'var(--brass)' }} />
            <span>Bias (MW)</span>
          </div>
        </div>
      </div>
      <div className="chart-body">
        <div className="chart-wrapper" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={horizonBuckets} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
              <CartesianGrid stroke="var(--rule)" vertical={false} />
              <XAxis
                dataKey="bucket"
                stroke="var(--text-dim)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                dy={8}
              />
              <YAxis
                stroke="var(--text-dim)"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: 'var(--hairline-strong)' }}
                tickFormatter={(v) => `${Math.round(v)}`}
                width={56}
              />
              <ReferenceLine y={0} stroke="var(--hairline-strong)" />
              <Tooltip content={<HorizonTooltip />} />
              <Bar
                dataKey="mae_mw"
                name="MAE"
                fill="var(--fc)"
                radius={[2, 2, 0, 0]}
                isAnimationActive={false}
              />
              <Bar
                dataKey="bias_mw"
                name="Bias"
                fill="var(--brass)"
                radius={[2, 2, 0, 0]}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  return (
    <div className="accuracy-charts">
      {/* Chart view switcher */}
      <div className="tabs" role="tablist" aria-label="Chart views">
        <button
          type="button"
          className={`tab-btn ${activeView === 'line' ? 'is-active' : ''}`}
          onClick={() => setActiveView('line')}
          role="tab"
          aria-selected={activeView === 'line'}
        >
          Forecast vs actual
        </button>
        <button
          type="button"
          className={`tab-btn ${activeView === 'error' ? 'is-active' : ''}`}
          onClick={() => setActiveView('error')}
          role="tab"
          aria-selected={activeView === 'error'}
        >
          Hourly error
        </button>
        <button
          type="button"
          className={`tab-btn ${activeView === 'horizon' ? 'is-active' : ''}`}
          onClick={() => setActiveView('horizon')}
          role="tab"
          aria-selected={activeView === 'horizon'}
        >
          Lead-time horizon
        </button>
        <button
          type="button"
          className={`tab-btn ${activeView === 'all' ? 'is-active' : ''}`}
          onClick={() => setActiveView('all')}
          role="tab"
          aria-selected={activeView === 'all'}
        >
          View all
        </button>
      </div>

      {activeView === 'line' && renderLineChart(380)}
      {activeView === 'error' && renderErrorChart(380)}
      {activeView === 'horizon' && renderHorizonChart(380)}

      {activeView === 'all' && (
        <div className="all-views">
          {renderLineChart(320)}
          <div className="split-2">
            {renderErrorChart(280)}
            {renderHorizonChart(280)}
          </div>
        </div>
      )}
    </div>
  );
};
