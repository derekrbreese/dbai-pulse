import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'
import PlayerHeadshot from './PlayerHeadshot'
import './FlagsBrowser.css'

const FLAG_EXPLANATIONS = {
    BREAKOUT_CANDIDATE: 'L3W average is 50%+ above projection — significantly outproducing expectations',
    TRENDING_UP: 'L3W average is 20%+ above projection — on an upward trajectory',
    UNDERPERFORMING: 'L3W average is below 80% of projection — not meeting expectations',
    DECLINING_ROLE: 'L3W average is below 70% of projection — significant production drop',
    HIGH_CEILING: 'Best recent week was 2x+ their projection — spike week potential',
    BOOM_BUST: 'Best week is 2x+ their worst week — high variance, unpredictable',
    CONSISTENT: 'All recent weeks within ±20% of average — reliable, low-variance scorer',
}

const FLAGS = [
    { id: 'BREAKOUT_CANDIDATE', label: '🚀 Breakout', description: 'Players outperforming projections by 50%+ over last 3 weeks' },
    { id: 'TRENDING_UP', label: '📈 Trending Up', description: 'Players outperforming projections by 20%+ over last 3 weeks' },
    { id: 'CONSISTENT', label: '✅ Consistent', description: 'All recent weeks within ±20% of their average — reliable scorers' },
    { id: 'HIGH_CEILING', label: '🎯 High Ceiling', description: 'Had at least one week at 2x+ their projection — spike potential' },
    { id: 'BOOM_BUST', label: '🎰 Boom/Bust', description: 'Best week is 2x+ their worst — high variance, start at your own risk' },
    { id: 'UNDERPERFORMING', label: '📉 Under', description: 'Scoring below 80% of projection — underdelivering expectations' },
    { id: 'DECLINING_ROLE', label: '⚠️ Declining', description: 'Scoring below 70% of projection — significant role or usage reduction' },
]

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE']

function FlagsBrowser({ onPlayerSelect, navigate }) {
    const [selectedFlag, setSelectedFlag] = useState('BREAKOUT_CANDIDATE')
    const [selectedPosition, setSelectedPosition] = useState('ALL')
    const [players, setPlayers] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [seasonInfo, setSeasonInfo] = useState(null)

    useEffect(() => {
        async function fetchStatus() {
            try {
                const response = await apiFetch('/api/status')
                if (response.ok) {
                    const data = await response.json()
                    setSeasonInfo(data)
                }
            } catch (_err) {
                // Non-critical
            }
        }
        fetchStatus()
    }, [])

    const fetchPlayers = useCallback(async () => {
        setLoading(true)
        setError(null)

        try {
            const posParam = selectedPosition !== 'ALL' ? `&position=${selectedPosition}` : ''
            const response = await apiFetch(
                `/api/players/by-flag/${selectedFlag}?limit=30${posParam}`
            )
            if (!response.ok) {
                throw new Error('Failed to fetch players')
            }
            const data = await response.json()
            setPlayers(data.players || [])
        } catch (err) {
            setError(err.message)
            setPlayers([])
        } finally {
            setLoading(false)
        }
    }, [selectedFlag, selectedPosition])

    useEffect(() => {
        fetchPlayers()
    }, [fetchPlayers])

    const handleCardClick = (playerData) => {
        if (onPlayerSelect) {
            onPlayerSelect(playerData.player)
        }
    }

    return (
        <div className="flags-page">
            {/* Header */}
            <div className="flags-page-header">
                <div className="flags-title">
                    <span className="flags-icon">📊</span>
                    <div>
                        <h2>Trends & Insights</h2>
                        <p className="flags-subtitle">Discover breakout players and performance patterns</p>
                    </div>
                </div>
                {seasonInfo && (
                    <div className="flags-freshness">
                        <span className="freshness-dot" />
                        Week {seasonInfo.week} Data
                    </div>
                )}
            </div>

            {/* Flag Tabs */}
            <div className="flags-tabs">
                {FLAGS.map(flag => (
                    <button
                        key={flag.id}
                        className={`flag-tab ${selectedFlag === flag.id ? 'active' : ''}`}
                        onClick={() => setSelectedFlag(flag.id)}
                        title={flag.description}
                    >
                        {flag.label}
                    </button>
                ))}
            </div>

            {/* Position Filter */}
            <div className="position-filter">
                {POSITIONS.map(pos => (
                    <button
                        key={pos}
                        className={`position-btn ${selectedPosition === pos ? 'active' : ''}`}
                        onClick={() => setSelectedPosition(pos)}
                    >
                        {pos}
                    </button>
                ))}
            </div>

            {/* Results */}
            <div className="flags-results">
                {loading && (
                    <div className="flags-loading">
                        <div className="flags-spinner"></div>
                        <p>Finding players...</p>
                    </div>
                )}

                {error && (
                    <div className="flags-error">⚠️ {error}</div>
                )}

                {!loading && !error && players.length === 0 && (
                    <div className="flags-empty">
                        <p>No players found with this flag</p>
                    </div>
                )}

                {!loading && players.length > 0 && (
                    <div className="player-grid">
                        {players.map(p => (
                            <div
                                key={p.player.sleeper_id}
                                className="player-card-mini"
                                onClick={() => handleCardClick(p)}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => { if (e.key === 'Enter') handleCardClick(p) }}
                            >
                                <div className="player-card-header">
                                    <PlayerHeadshot espnId={p.player.espn_id} position={p.player.position} size={24} />
                                    <span className="flags-player-team">{p.player.team || 'FA'}</span>
                                    {p.player.injury_status && (
                                        <span className={`injury-badge ${p.player.injury_status.toLowerCase().replace('_', '')}`}>
                                            {p.player.injury_status}
                                        </span>
                                    )}
                                    <span className="hover-reveal">View Details</span>
                                </div>
                                <div className="flags-player-name">{p.player.name}</div>
                                <div className="player-stats">
                                    <div className="stat">
                                        <span className="flags-stat-label">L3W Avg</span>
                                        <span className="flags-stat-value">
                                            {p.recent_performance?.avg_points?.toFixed(1) || '0'} pts
                                        </span>
                                    </div>
                                    <div className="stat">
                                        <span className="flags-stat-label">Trend</span>
                                        <span className={`flags-stat-value trend-${p.recent_performance?.trend}`}>
                                            {p.recent_performance?.trend || 'stable'}
                                            {p.recent_performance?.trend_delta != null && (
                                                <span className={`trend-delta ${p.recent_performance.trend_delta >= 0 ? 'positive' : 'negative'}`}>
                                                    {' '}{p.recent_performance.trend_delta >= 0 ? '+' : ''}{p.recent_performance.trend_delta}
                                                </span>
                                            )}
                                        </span>
                                    </div>
                                    {p.recent_performance?.volatility_score != null && (
                                        <div className="stat">
                                            <span className="flags-stat-label">Volatility</span>
                                            <span className={`flags-stat-value ${
                                                p.recent_performance.volatility_score < 0.25 ? 'trend-improving' :
                                                p.recent_performance.volatility_score < 0.5 ? 'trend-stable' : 'trend-declining'
                                            }`}>
                                                {(p.recent_performance.volatility_score * 100).toFixed(0)}%
                                            </span>
                                        </div>
                                    )}
                                </div>
                                <div className="player-flags">
                                    {p.performance_flags?.map(flag => (
                                        <span key={flag} className="mini-flag" title={FLAG_EXPLANATIONS[flag] || flag}>{flag}</span>
                                    ))}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="flags-footer">
                <span className="flags-count">
                    Found {players.length} player{players.length !== 1 ? 's' : ''}
                </span>
            </div>
        </div>
    )
}

export default FlagsBrowser
