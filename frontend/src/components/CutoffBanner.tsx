import React from 'react';

interface CutoffBannerProps {
  cutoffTime: string | null;
  earliestPublish: string | null;
  latestPublish: string | null;
  cutoffHourUtc: number;
  targetDate: string;
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Formats an ISO UTC timestamp as "14 Jan · 09:00 UTC". Parsed from the raw
 * string (not the Date object) so the wall-clock UTC value is preserved. */
function fmtUtc(iso: string | null): string {
  if (!iso) return '—';
  const month = MONTHS[Number(iso.slice(5, 7)) - 1];
  return month ? `${iso.slice(8, 10)} ${month} · ${iso.slice(11, 16)} UTC` : iso;
}

/** Formats a plain "YYYY-MM-DD" target date as "15 Jan 2026". */
function fmtDay(day: string): string {
  const month = MONTHS[Number(day.slice(5, 7)) - 1];
  return month ? `${day.slice(8, 10)} ${month} ${day.slice(0, 4)}` : day;
}

export const CutoffBanner: React.FC<CutoffBannerProps> = ({
  cutoffTime,
  earliestPublish,
  latestPublish,
  cutoffHourUtc,
  targetDate,
}) => {
  const vintage =
    earliestPublish === latestPublish
      ? fmtUtc(earliestPublish)
      : `${fmtUtc(earliestPublish)} → ${fmtUtc(latestPublish)}`;

  return (
    <section className="panel decision-block" aria-label="Forecast decision parameters">
      <div className="panel-head">
        <h2 className="panel-kicker">Decision record</h2>
      </div>
      <div className="decision-rows">
        <div className="decision-row">
          <div className="decision-label">Target delivery day</div>
          <div className="decision-value tabular-nums">{fmtDay(targetDate)}</div>
        </div>
        <div className="decision-row">
          <div className="decision-label">Gate cutoff (D-1)</div>
          <div className="decision-value tabular-nums brass">
            {fmtUtc(cutoffTime)}
          </div>
        </div>
        <div className="decision-row">
          <div className="decision-label">Selected forecast vintage</div>
          <div className="decision-value tabular-nums">{vintage}</div>
        </div>
      </div>
      <p className="decision-note">
        Latest Elexon WINDFOR snapshot published before gate closure. After{' '}
        {String(cutoffHourUtc).padStart(2, '0')}:00 UTC on D-1 the desk buys on this forecast it
        cannot see anything newer.
      </p>
    </section>
  );
};
