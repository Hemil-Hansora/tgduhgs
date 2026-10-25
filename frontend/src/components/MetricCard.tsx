import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  tooltip: string;
  subtitle?: string;
  valueColor?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  unit,
  tooltip,
  subtitle,
  valueColor,
}) => {
  return (
    <div className="stat" style={{ '--accent': valueColor } as React.CSSProperties}>
      <div className="stat-head">
        <span className="stat-label">{title}</span>
        <button
          type="button"
          className="trigger"
          tabIndex={0}
          aria-label={`${title}: ${tooltip}`}
        >
          ?
          <span className="tooltip-popover" role="tooltip">
            {tooltip}
          </span>
        </button>
      </div>

      <div
        className="stat-value tabular-nums"
        style={valueColor && valueColor !== 'var(--brass)' ? { color: valueColor } : undefined}
      >
        {typeof value === 'number' ? Math.round(value).toLocaleString('en-GB') : value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>

      {subtitle && <div className="stat-sub">{subtitle}</div>}
    </div>
  );
};
