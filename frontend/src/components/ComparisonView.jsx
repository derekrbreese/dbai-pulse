import { useState } from 'react'
import { apiFetch } from '../api/client'
import PlayerSlot from './PlayerSlot'
import ComparisonResult from './ComparisonResult'
import './ComparisonView.css'

function ComparisonView() {
    const [playerA, setPlayerA] = useState(null)
    const [playerB, setPlayerB] = useState(null)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const runComparison = async () => {
        if (!playerA || !playerB) return

        setLoading(true)
        setError(null)

        try {
            const response = await apiFetch(
                `/api/players/compare/${playerA.sleeper_id}/${playerB.sleeper_id}`
            )
            if (!response.ok) {
                throw new Error('Failed to compare players')
            }
            const data = await response.json()
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="comparison-page">
            {/* Header */}
            <div className="comparison-page-header">
                <div className="comparison-title">
                    <span className="comparison-icon">🔄</span>
                    <div>
                        <h2>Compare Players</h2>
                        <p className="comparison-subtitle">Head-to-head Gemini analysis</p>
                    </div>
                </div>
            </div>

            {/* Player Slots */}
            <div className="comparison-slots">
                <PlayerSlot
                    label="Player A"
                    player={playerA}
                    onSelect={setPlayerA}
                />
                <div className="vs-divider">
                    <span className="vs-text">VS</span>
                </div>
                <PlayerSlot
                    label="Player B"
                    player={playerB}
                    onSelect={setPlayerB}
                />
            </div>

            {/* Compare Button */}
            <div className="comparison-action">
                <button
                    className="compare-button"
                    onClick={runComparison}
                    disabled={!playerA || !playerB || loading}
                >
                    {loading ? (
                        <>
                            <div className="compare-spinner"></div>
                            <span>Analyzing...</span>
                        </>
                    ) : (
                        <>
                            <span>⚡</span>
                            <span>Compare Players</span>
                        </>
                    )}
                </button>
            </div>

            {error && <div className="comparison-error">⚠️ {error}</div>}

            {/* Results */}
            {result && (
                <div className="comparison-results-wrapper">
                    <ComparisonResult data={result} />
                </div>
            )}
        </div>
    )
}

export default ComparisonView
