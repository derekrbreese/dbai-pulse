import './ComparisonResult.css'

function ComparisonResult({ data }) {
    const { player_a, player_b, winner, winner_name, conviction, reasoning,
        key_advantages_a, key_advantages_b, matchup_edge, sources_used } = data

    const getWinnerClass = () => {
        if (winner === 'A') return 'winner-a'
        if (winner === 'B') return 'winner-b'
        return 'winner-toss'
    }

    const getConvictionColor = () => {
        switch (conviction) {
            case 'HIGH': return '#22c55e'
            case 'MEDIUM': return '#f59e0b'
            case 'LOW': return '#ef4444'
            default: return '#6b7280'
        }
    }

    return (
        <div className="comparison-result">
            {/* Winner Banner */}
            <div className={`winner-banner ${getWinnerClass()}`}>
                <span className="winner-icon">🏆</span>
                <div className="winner-info">
                    <span className="winner-label">Winner</span>
                    <span className="winner-name">{winner_name}</span>
                </div>
                <span
                    className="conviction-badge"
                    style={{ backgroundColor: getConvictionColor() }}
                >
                    {conviction} CONVICTION
                </span>
            </div>

            {/* Side by Side Stats */}
            <div className="comparison-stats">
                <div className={`comparison-player ${winner === 'A' ? 'is-winner' : ''}`}>
                    <h4>{player_a.player.name}</h4>
                    <div className="stat-row">
                        <span className="stat-label">Projection</span>
                        <span className="stat-value">{player_a.projection.adjusted_projection?.toFixed(1) || player_a.projection.sleeper_projection?.toFixed(1)} pts</span>
                    </div>
                    {player_a.recent_performance && (
                        <div className="stat-row">
                            <span className="stat-label">L3W Avg</span>
                            <span className="stat-value">{player_a.recent_performance.avg_points} pts</span>
                        </div>
                    )}
                    {key_advantages_a.length > 0 && (
                        <div className="advantages">
                            <span className="advantages-label">✅ Advantages</span>
                            <ul>
                                {key_advantages_a.map((adv, i) => (
                                    <li key={i}>{adv}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>

                <div className={`comparison-player ${winner === 'B' ? 'is-winner' : ''}`}>
                    <h4>{player_b.player.name}</h4>
                    <div className="stat-row">
                        <span className="stat-label">Projection</span>
                        <span className="stat-value">{player_b.projection.adjusted_projection?.toFixed(1) || player_b.projection.sleeper_projection?.toFixed(1)} pts</span>
                    </div>
                    {player_b.recent_performance && (
                        <div className="stat-row">
                            <span className="stat-label">L3W Avg</span>
                            <span className="stat-value">{player_b.recent_performance.avg_points} pts</span>
                        </div>
                    )}
                    {key_advantages_b.length > 0 && (
                        <div className="advantages">
                            <span className="advantages-label">✅ Advantages</span>
                            <ul>
                                {key_advantages_b.map((adv, i) => (
                                    <li key={i}>{adv}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            </div>

            {/* Reasoning */}
            <div className="comparison-reasoning">
                <h4>💭 Analysis</h4>
                <p>{reasoning}</p>
            </div>

            {/* Matchup Edge */}
            {matchup_edge && (
                <div className="matchup-edge">
                    <h4>🏈 Matchup Edge</h4>
                    <p>{matchup_edge}</p>
                </div>
            )}

            {/* Sources */}
            {sources_used && sources_used.length > 0 && (
                <div className="comparison-sources">
                    <span>Sources: {sources_used.join(', ')}</span>
                </div>
            )}
        </div>
    )
}

export default ComparisonResult
