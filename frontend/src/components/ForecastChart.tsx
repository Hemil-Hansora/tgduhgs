import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { ForecastSlot } from '../types';

interface ForecastChartProps {
  slots: ForecastSlot[];
  targetDate: string;
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

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload || !payload.length) return null;

  const forecastItem = payload.find((p) => p.dataKey === 'forecast_mw');
  const actualItem = payload.find((p) => p.dataKey === 'actual_mw');

  const fVal = forecastItem ? forecastItem.value : null;
  const aVal = actualItem && typeof actualItem.value === 'number' ? actualItem.value : null;
  const diff = fVal !== null && aVal !== null ? fVal - aVal : null;

  return (
    <div className="tooltip-panel" role="tooltip">
      <div className="tooltip-kicker tabular-nums">{label} UTC</div>
      {fVal !== null && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--fc)' }} />
            Forecast
          </span>
          <span className="tooltip-val tabular-nums">{Math.round(fVal).toLocaleString('en-GB')} MW</span>
        </div>
      )}

      {aVal !== null && (
        <div className="tooltip-row">
          <span className="tooltip-label">
            <span className="dot" style={{ backgroundColor: 'var(--act)' }} />
            Actual
          </span>
          <span className="tooltip-val tabular-nums">{Math.round(aVal).toLocaleString('en-GB')} MW</span>
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

export const ForecastChart: React.FC<ForecastChartProps> = ({ slots, targetDate }) => {
  const chartData = slots.map((slot) => ({
    time: slot.startTime.substring(11, 16),
    fullTime: slot.startTime,
    forecast_mw: slot.forecast_mw,
    actual_mw: slot.actual_mw,
  }));

  const hasActuals = slots.some((s) => s.actual_mw !== null);

  return (
    <div className="panel">
      <div className="panel-head">
        <h2 className="chart-title">Hourly wind generation · {targetDate}</h2>
        <div className="legend">
          <div className="legend-item">
            <span className="legend-line forecast" />
            <span>Day-ahead forecast (MW)</span>
          </div>
          {hasActuals && (
            <div className="legend-item">
              <span className="legend-line actual" />
              <span>Actual outturn (MW)</span>
            </div>
          )}
        </div>
      </div>

      <div className="chart-body">
        <div className="chart-wrapper">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 20 }}>
              <CartesianGrid stroke="var(--rule)" vertical={false} />
              <XAxis
                dataKey="time"
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
                tickFormatter={(val) => `${(val / 1000).toFixed(1)}k`}
                width={56}
              />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="forecast_mw"
                name="Forecast"
                stroke="var(--fc)"
                strokeWidth={2}
                dot={{ r: 2, fill: 'var(--fc)' }}
                activeDot={{ r: 5 }}
                isAnimationActive={false}
              />
              {hasActuals && (
                <Line
                  type="monotone"
                  dataKey="actual_mw"
                  name="Actual"
                  stroke="var(--act)"
                  strokeWidth={2}
                  dot={{ r: 2, fill: 'var(--act)' }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
