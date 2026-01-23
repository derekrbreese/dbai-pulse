import './PulseModal.css'

function PulseModal({ data, playerName: _playerName, onClose }) {
    const { gemini_analysis, player } = data

    const getConvictionColor = (conviction) => {
        switch (conviction) {
            case 'HIGH': return '#22c55e'
            case 'MEDIUM-HIGH': return '#84cc16'
            case 'MIXED': return '#f59e0b'
            case 'MEDIUM-LOW': return '#f97316'
            case 'LOW': return '#ef4444'
            default: return '#6b7280'
        }
    }

    const getRecommendationIcon = (recommendation) => {
        switch (recommendation) {
            case 'START': return '🚀'
            case 'SIT': return '🪑'
            case 'FLEX': return '🤔'
            default: return '📊'
        }
    }

    const getRiskColor = (risk) => {
        switch (risk) {
            case 'LOW': return '#22c55e'
            case 'MODERATE': return '#f59e0b'
            case 'HIGH': return '#ef4444'
            default: return '#6b7280'
        }
    }

    return (
        <div className="pulse-modal-overlay" onClick={onClose}>
            <div className="pulse-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="pulse-modal-header">
                    <div className="pulse-modal-title">
                        <span className="pulse-icon-large">🔮</span>
                        <div>
                            <h2>The Pulse</h2>
                            <p className="pulse-subtitle">AI-Powered Fantasy Analysis</p>
                        </div>
                    </div>
                    <button className="pulse-close" onClick={onClose}>✕</button>
                </div>

                {/* Player Info */}
                <div className="pulse-player-info">
                    <h3>{player.player.name}</h3>
                    <span className={`position-badge position-${player.player.position.toLowerCase()}`}>
                        {player.player.position}
                    </span>
                    <span className="team-badge">{player.player.team}</span>
                </div>

                {/* Recommendation Card */}
                <div className="pulse-recommendation-card">
                    <div className="recommendation-header">
                        <span className="recommendation-icon">
                            {getRecommendationIcon(gemini_analysis.recommendation)}
                        </span>
                        <div>
                            <div className="recommendation-label">Recommendation</div>
                            <div className="recommendation-value">{gemini_analysis.recommendation}</div>
                        </div>
                    </div>

                    <div className="conviction-bar">
                        <div className="conviction-label">Conviction</div>
                        <div className="conviction-badges">
                            <span
                                className="conviction-badge"
                                style={{ backgroundColor: getConvictionColor(gemini_analysis.conviction) }}
                            >
                                {gemini_analysis.conviction}
                            </span>
                            <span
                                className="risk-badge"
                                style={{ borderColor: getRiskColor(gemini_analysis.risk_level) }}
                            >
                                {gemini_analysis.risk_level} RISK
                            </span>
                        </div>
                    </div>

                    <div className="reasoning-section">
                        <div className="reasoning-label">💭 Analysis</div>
                        <p className="reasoning-text">{gemini_analysis.reasoning}</p>
                    </div>
                </div>

                {/* Key Factors */}
                <div className="pulse-section">
                    <h4 className="section-title">🎯 Key Factors</h4>
                    <ul className="key-factors-list">
                        {gemini_analysis.key_factors.map((factor, index) => (
                            <li key={index}>{factor}</li>
                        ))}
                    </ul>
                </div>

                {/* Expert Consensus */}
                {gemini_analysis.expert_consensus && (
                    <div className="pulse-section">
                        <h4 className="section-title">📺 Expert Consensus</h4>
                        <p className="expert-text">{gemini_analysis.expert_consensus}</p>
                    </div>
                )}

                {/* Expert Video Sources */}
                {data.expert_takes && data.expert_takes.length > 0 && (
                    <div className="pulse-section">
                        <h4 className="section-title">🎬 Expert Sources</h4>
                        <div className="expert-takes-grid">
                            {data.expert_takes.filter(take => take.mentioned).map((take, index) => (
                                <div key={index} className="expert-take-card mentioned">
                                    <div className="expert-take-source">{take.source}</div>
                                    <div className="expert-take-status">✓ Player mentioned</div>
                                    {take.reasoning && (
                                        <p className="expert-take-quote">"{take.reasoning}"</p>
                                    )}
                                </div>
                            ))}
                            {data.expert_takes.filter(take => !take.mentioned).length > 0 && (
                                <div className="expert-take-card not-mentioned">
                                    <div className="expert-take-source">Other Sources Checked</div>
                                    <div className="expert-take-status dim">
                                        {data.expert_takes.filter(take => !take.mentioned).map(t => t.source).join(', ')}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Data Sources / Citations */}
                <div className="pulse-citations">
                    <h4 className="section-title">📚 Data Sources</h4>
                    <ul className="citations-list">
                        <li>
                            <span className="citation-source">Google Search</span>
                            <span className="citation-detail">Live web search for current news & expert opinions</span>
                        </li>
                        <li>
                            <span className="citation-source">Sleeper API</span>
                            <span className="citation-detail">Player projections & stats, Week 16, 2025 NFL season</span>
                        </li>
                        {gemini_analysis.sources_used && gemini_analysis.sources_used.length > 0 && (
                            <li>
                                <span className="citation-source">Sources Found</span>
                                <span className="citation-detail">
                                    {gemini_analysis.sources_used.join(', ')}
                                </span>
                            </li>
                        )}
                        <li>
                            <span className="citation-source">Generated</span>
                            <span className="citation-detail">{new Date().toLocaleString()}</span>
                        </li>
                    </ul>
                </div>

                {/* Disclaimer */}
                <div className="pulse-footer">
                    <span>⚠️ For entertainment purposes only. Not financial advice.</span>
                </div>
            </div>
        </div>
    )
}

export default PulseModal
