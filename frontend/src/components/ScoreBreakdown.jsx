import './ScoreBreakdown.css'

function ScoreBreakdown({ score, breakdown }) {
  if (score == null) return null

  const rows = breakdown ? [
    { label: 'Base Projection', value: breakdown.base },
    { label: 'Recent Perf', value: breakdown.recent_adj },
    { label: 'Flag Bonus', value: breakdown.flag_bonus },
    { label: 'Risk Pref', value: breakdown.risk_adj },
    { label: 'Focus Pref', value: breakdown.focus_adj },
    { label: 'Injury Penalty', value: breakdown.injury_penalty },
  ] : []

  return (
    <span className="score-breakdown-wrapper">
      <span className="score-breakdown-trigger">
        Score {score.toFixed(1)}
      </span>
      {breakdown && (
        <span className="score-breakdown-tooltip">
          <span className="sbt-title">Score Breakdown</span>
          {rows.map(row => (
            <span key={row.label} className="sbt-row">
              <span className="sbt-label">{row.label}</span>
              <span className={`sbt-value${row.value > 0 ? ' positive' : row.value < 0 ? ' negative' : ''}`}>
                {row.value > 0 ? '+' : ''}{row.value.toFixed(1)}
              </span>
            </span>
          ))}
          <span className="sbt-divider" />
          <span className="sbt-row sbt-final">
            <span className="sbt-label">Final</span>
            <span className="sbt-value">{breakdown.final.toFixed(1)}</span>
          </span>
        </span>
      )}
    </span>
  )
}

export default ScoreBreakdown
