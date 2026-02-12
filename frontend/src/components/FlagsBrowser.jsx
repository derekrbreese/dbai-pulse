import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'
import PlayerHeadshot from './PlayerHeadshot'
import './FlagsBrowser.css'

const FLAGS = [
    { id: 'BREAKOUT_CANDIDATE', label: '🚀 Breakout', description: 'Outperforming projections by 50%+' },
    { id: 'TRENDING_UP', label: '📈 Trending Up', description: 'Outperforming projections by 20%+' },
    { id: 'CONSISTENT', label: '✅ Consistent', description: 'Low variance, reliable scorer' },
    { id: 'HIGH_CEILING', label: '🎯 High Ceiling', description: 'Spike week potential' },
    { id: 'BOOM_BUST', label: '🎰 Boom/Bust', description: 'High variance player' },
    { id: 'UNDERPERFORMING', label: '📉 Under', description: 'Below projections' },
    { id: 'DECLINING_ROLE', label: '⚠️ Declining', description: 'Significant role reduction' },
]

const POSITIONS = ['ALL', 'QB', 'RB', 'WR', 'TE']

function FlagsBrowser({ onPlayerSelect, navigate }) {
    const [selectedFlag, setSelectedFlag] = useState('BREAKOUT_CANDIDATE')
    const [selectedPosition, setSelectedPosition] = useState('ALL')
    const [players, setPlayers] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

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
        if (navigate) {
            navigate('search')
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
                            <div key={p.player.sleeper_id} className="player-card-mini" onClick={() => handleCardClick(p)}>
                                <div className="player-card-header">
                                    <PlayerHeadshot espnId={p.player.espn_id} position={p.player.position} size={24} />
                                    <span className="flags-player-team">{p.player.team || 'FA'}</span>
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
                                        </span>
                                    </div>
                                </div>
                                <div className="player-flags">
                                    {p.performance_flags?.map(flag => (
                                        <span key={flag} className="mini-flag">{flag}</span>
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
