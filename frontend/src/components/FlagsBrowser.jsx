import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
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

function FlagsBrowser({ onClose }) {
    const [selectedFlag, setSelectedFlag] = useState('BREAKOUT_CANDIDATE')
    const [selectedPosition, setSelectedPosition] = useState('ALL')
    const [players, setPlayers] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    useEffect(() => {
        fetchPlayers()
    }, [selectedFlag, selectedPosition])

    const fetchPlayers = async () => {
        setLoading(true)
        setError(null)

        try {
            const posParam = selectedPosition !== 'ALL' ? `&position=${selectedPosition}` : ''
            const response = await fetch(
                `http://localhost:8000/api/players/by-flag/${selectedFlag}?limit=30${posParam}`
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
    }

    const getPositionClass = (position) => {
        return `position-${position?.toLowerCase()}`
    }

    const modalContent = (
        <div className="flags-overlay" onClick={onClose}>
            <div className="flags-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="flags-header">
                    <div className="flags-title">
                        <span className="flags-icon">📊</span>
                        <div>
                            <h2>Trends & Insights</h2>
                            <p className="flags-subtitle">Discover breakout players and performance patterns</p>
                        </div>
                    </div>
                    <button className="flags-close" onClick={onClose}>✕</button>
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
                                <div key={p.player.sleeper_id} className="player-card-mini">
                                    <div className="player-card-header">
                                        <span className={`player-position ${getPositionClass(p.player.position)}`}>
                                            {p.player.position}
                                        </span>
                                        <span className="player-team">{p.player.team || 'FA'}</span>
                                    </div>
                                    <div className="player-name">{p.player.name}</div>
                                    <div className="player-stats">
                                        <div className="stat">
                                            <span className="stat-label">L3W Avg</span>
                                            <span className="stat-value">
                                                {p.recent_performance?.avg_points?.toFixed(1) || '0'} pts
                                            </span>
                                        </div>
                                        <div className="stat">
                                            <span className="stat-label">Trend</span>
                                            <span className={`stat-value trend-${p.recent_performance?.trend}`}>
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
        </div>
    )

    return createPortal(modalContent, document.body)
}

export default FlagsBrowser
