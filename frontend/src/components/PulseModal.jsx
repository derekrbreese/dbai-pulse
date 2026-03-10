import { useEffect, useRef, useState } from 'react'
import './PulseModal.css'

function PulseModal({ data, playerName: _playerName, onClose }) {
    const { gemini_analysis, player } = data
    const isOffseason = data.season_type && data.season_type !== 'regular'
    const modalRef = useRef(null)
    const [sourcesExpanded, setSourcesExpanded] = useState(false)

    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') onClose()
        }
        document.addEventListener('keydown', handleKeyDown)
        modalRef.current?.focus()
        return () => document.removeEventListener('keydown', handleKeyDown)
    }, [onClose])

    const getRecommendationColor = (recommendation) => {
        switch (recommendation) {
            case 'START': case 'BUY': return '#22c55e'
            case 'SIT': case 'SELL': return '#ef4444'
            case 'FLEX': case 'HOLD': return '#f59e0b'
            default: return '#6b7280'
        }
    }

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
            case 'BUY': return '📈'
            case 'HOLD': return '✊'
            case 'SELL': return '📉'
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
            <div
                className="pulse-modal"
                ref={modalRef}
                role="dialog"
                aria-modal="true"
                aria-label={`Pulse analysis for ${player.player.name}`}
                tabIndex={-1}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="pulse-modal-header">
                    <div className="pulse-modal-title">
                        <span className="pulse-icon-large">🔮</span>
                        <div>
                            <h2>The Pulse</h2>
                            <p className="pulse-subtitle">
                                {isOffseason
                                    ? `${data.season || 2025} Offseason Analysis`
                                    : 'AI-Powered Fantasy Analysis'}
                            </p>
                        </div>
                    </div>
                    <button className="pulse-close" onClick={onClose} aria-label="Close analysis">✕</button>
                </div>

                {/* Player Info */}
                <div className="pulse-player-info">
                    <h3>{player.player.name}</h3>
                    <span className={`position-badge position-${player.player.position.toLowerCase()}`}>
                        {player.player.position}
                    </span>
                    <span className="team-badge">{player.player.team}</span>
                    {player.player.injury_status && (
                        <span className={`injury-badge ${player.player.injury_status.toLowerCase().replace('_', '')}`}>
                            {player.player.injury_status}
                        </span>
                    )}
                </div>

                {/* Recommendation Card */}
                <div className="pulse-recommendation-card">
                    <div className="recommendation-header">
                        <span className="recommendation-icon">
                            {getRecommendationIcon(gemini_analysis.recommendation)}
                        </span>
                        <div>
                            <div className="recommendation-label">{isOffseason ? 'Dynasty Value' : 'Recommendation'}</div>
                            <div className="recommendation-value" style={{ color: getRecommendationColor(gemini_analysis.recommendation) }}>{gemini_analysis.recommendation}</div>
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

                    {gemini_analysis.ecr_rank != null && (
                        <div className="ecr-row">
                            <span className="ecr-label">ECR</span>
                            <span className="ecr-rank">#{gemini_analysis.ecr_rank}</span>
                            {(gemini_analysis.ecr_best != null || gemini_analysis.ecr_worst != null) && (
                                <span className="ecr-range">
                                    (#{gemini_analysis.ecr_best ?? '?'} – #{gemini_analysis.ecr_worst ?? '?'})
                                </span>
                            )}
                        </div>
                    )}

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
                                        <p className="expert-take-quote">{take.reasoning}</p>
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
                    <button
                        className="sources-toggle"
                        onClick={() => setSourcesExpanded(!sourcesExpanded)}
                        aria-expanded={sourcesExpanded}
                    >
                        <h4 className="section-title" style={{ margin: 0 }}>📚 Data Sources</h4>
                        <span className={`sources-chevron ${sourcesExpanded ? 'expanded' : ''}`}>▾</span>
                    </button>
                    {sourcesExpanded && (
                        <div className="sources-panel">
                            <div className="source-category">
                                <span className="citation-source">AI Analysis</span>
                                <span className="citation-detail">Gemini 2.5 Flash with Google Search grounding</span>
                            </div>
                            <div className="source-category">
                                <span className="citation-source">Data APIs</span>
                                <span className="citation-detail">
                                    Sleeper — {isOffseason
                                        ? `projections & stats, ${data.season || 2025} NFL season`
                                        : `projections & stats, Week ${data.week || '?'}, ${data.season || 2025}`}
                                </span>
                            </div>
                            {gemini_analysis.sources_used && gemini_analysis.sources_used.length > 0 && (
                                <div className="source-category">
                                    <span className="citation-source">Web Sources</span>
                                    <div className="web-sources-list">
                                        {gemini_analysis.sources_used.map((source, i) => {
                                            try {
                                                const url = new URL(source)
                                                return (
                                                    <a key={i} href={source} target="_blank" rel="noopener noreferrer" className="web-source-link">
                                                        {url.hostname.replace('www.', '')}
                                                    </a>
                                                )
                                            } catch {
                                                return <span key={i} className="web-source-text">{source}</span>
                                            }
                                        })}
                                    </div>
                                </div>
                            )}
                            {data.expert_takes && data.expert_takes.filter(t => t.mentioned).length > 0 && (
                                <div className="source-category">
                                    <span className="citation-source">Expert Video Sources</span>
                                    <span className="citation-detail">
                                        {data.expert_takes.filter(t => t.mentioned).map(t => t.source).join(', ')}
                                    </span>
                                </div>
                            )}
                            <div className="source-category last">
                                <span className="citation-source">Generated</span>
                                <span className="citation-detail">{new Date().toLocaleString()}</span>
                            </div>
                        </div>
                    )}
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
