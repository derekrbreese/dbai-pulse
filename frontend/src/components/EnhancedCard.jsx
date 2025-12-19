import './EnhancedCard.css'

function EnhancedCard({ data }) {
    const { player, projection, recent_performance, performance_flags, context_message, on_bye } = data

    // Get flag color
    const getFlagColor = (flag) => {
        if (flag.includes('BREAKOUT') || flag.includes('TRENDING_UP')) return '#22c55e'
        if (flag.includes('DECLINING') || flag.includes('UNDERPERFORMING')) return '#ef4444'
        if (flag.includes('CEILING')) return '#f59e0b'
        if (flag.includes('CONSISTENT')) return '#3b82f6'
        if (flag.includes('BYE')) return '#6b7280'
        return '#8b5cf6'
    }

    // Get position color
    const getPositionColor = (position) => {
        const colors = {
            QB: '#e74c3c',
            RB: '#27ae60',
            WR: '#3498db',
            TE: '#f39c12',
            K: '#9b59b6',
            DEF: '#34495e',
        }
        return colors[position] || '#7f8c8d'
    }

    // Format projection display
    const projectionDisplay = projection.adjusted_projection ?? projection.sleeper_projection
    const hasAdjustment = projection.adjusted_projection &&
        projection.adjusted_projection !== projection.sleeper_projection

    return (
        <div className={`enhanced-card ${on_bye ? 'on-bye' : ''}`}>
            {/* Header */}
            <div className="card-header">
                <div className="player-info">
                    <span
                        className="position-badge large"
                        style={{ backgroundColor: getPositionColor(player.position) }}
                    >
                        {player.position}
                    </span>
                    <div className="player-details">
                        <h2 className="player-name">{player.name}</h2>
                        <span className="player-team">{player.team || 'Free Agent'}</span>
                    </div>
                </div>
                {on_bye && (
                    <div className="bye-badge">
                        <span>🚫 BYE WEEK</span>
                    </div>
                )}
            </div>

            {/* Projection */}
            <div className="card-section projection-section">
                <h3>Projection</h3>
                <div className="projection-display">
                    <span className="projection-value">{projectionDisplay.toFixed(1)}</span>
                    <span className="projection-label">pts</span>
                    {hasAdjustment && (
                        <span className="projection-adjustment">
                            (base: {projection.sleeper_projection.toFixed(1)})
                        </span>
                    )}
                </div>
            </div>

            {/* Recent Performance */}
            {recent_performance && recent_performance.weeks_analyzed > 0 && (
                <div className="card-section performance-section">
                    <h3>Recent Performance</h3>
                    <div className="performance-stats">
                        <div className="stat-item">
                            <span className="stat-value">{recent_performance.avg_points}</span>
                            <span className="stat-label">L{recent_performance.weeks_analyzed}W Avg</span>
                        </div>
                        <div className="stat-item">
                            <span className={`stat-value trend-${recent_performance.trend}`}>
                                {recent_performance.trend === 'improving' && '📈'}
                                {recent_performance.trend === 'declining' && '📉'}
                                {recent_performance.trend === 'stable' && '➡️'}
                            </span>
                            <span className="stat-label">Trend</span>
                        </div>
                        {recent_performance.weekly_points.length > 0 && (
                            <div className="stat-item">
                                <span className="stat-value">
                                    {Math.max(...recent_performance.weekly_points).toFixed(1)}
                                </span>
                                <span className="stat-label">Best Week</span>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* Performance Flags */}
            {performance_flags.length > 0 && (
                <div className="card-section flags-section">
                    <h3>Performance Flags</h3>
                    <div className="flags-container">
                        {performance_flags.map((flag, idx) => (
                            <span
                                key={idx}
                                className="flag-chip"
                                style={{ backgroundColor: getFlagColor(flag) }}
                            >
                                {flag.replace(/_/g, ' ')}
                            </span>
                        ))}
                    </div>
                </div>
            )}

            {/* Context */}
            {context_message && (
                <div className="card-section context-section">
                    <p className="context-message">{context_message}</p>
                </div>
            )}
        </div>
    )
}

export default EnhancedCard
