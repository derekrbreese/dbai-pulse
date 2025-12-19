import { useState } from 'react'
import { createPortal } from 'react-dom'
import PlayerSlot from './PlayerSlot'
import ComparisonResult from './ComparisonResult'
import './ComparisonView.css'

function ComparisonView({ onClose }) {
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
            const response = await fetch(
                `http://localhost:8000/api/players/compare/${playerA.sleeper_id}/${playerB.sleeper_id}`
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

    const modalContent = (
        <div className="comparison-overlay" onClick={onClose}>
            <div className="comparison-modal" onClick={(e) => e.stopPropagation()}>
                {/* Header */}
                <div className="comparison-header">
                    <div className="comparison-title">
                        <span className="comparison-icon">🔄</span>
                        <div>
                            <h2>Compare Players</h2>
                            <p className="comparison-subtitle">Head-to-head Gemini analysis</p>
                        </div>
                    </div>
                    <button className="comparison-close" onClick={onClose}>✕</button>
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

                {error && <div className="comparison-error">⚠️ {error}</div>}

                {/* Results */}
                {result && <ComparisonResult data={result} />}
            </div>
        </div>
    )

    return createPortal(modalContent, document.body)
}

export default ComparisonView
