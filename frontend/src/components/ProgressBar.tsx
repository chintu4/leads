import React from "react";

type Props = { progress?: number };

export default function ProgressBar({ progress = 0 }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <div
      className="progress-bar-wrap"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
    >
      <div className="progress-bar" style={{ width: `${pct}%` }} />
      <div className="progress-label">{pct}%</div>
    </div>
  );
}
