import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../api/client'
import PlayerSlot from './PlayerSlot'
import ComparisonResult from './ComparisonResult'
import './ComparisonView.css'

async function loadPlayerById(sleeperId) {
    const response = await apiFetch(`/api/players/${sleeperId}`)
    if (!response.ok) return null
    const data = await response.json()
    return data?.player || null
}

function ComparisonView({ params = {} }) {
    const [playerA, setPlayerA] = useState(null)
    const [playerB, setPlayerB] = useState(null)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [prefilling, setPrefilling] = useState(false)
    const [error, setError] = useState(null)
    const prefilledRef = useRef(false)

    const runComparison = async (a, b) => {
        const pA = a || playerA
        const pB = b || playerB
        if (!pA || !pB) return

        setLoading(true)
        setError(null)

        try {
            const response = await apiFetch(
                `/api/players/compare/${pA.sleeper_id}/${pB.sleeper_id}`
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

    // Auto-load players from URL params on mount
    useEffect(() => {
        if (prefilledRef.current) return
        if (!params.a && !params.b) return
        prefilledRef.current = true

        const prefill = async () => {
            setPrefilling(true)
            try {
                const [loadedA, loadedB] = await Promise.all([
                    params.a ? loadPlayerById(params.a) : null,
                    params.b ? loadPlayerById(params.b) : null,
                ])
                if (loadedA) setPlayerA(loadedA)
                if (loadedB) setPlayerB(loadedB)

                // Auto-run if both loaded
                if (loadedA && loadedB) {
                    await runComparison(loadedA, loadedB)
                }
            } catch (err) {
                setError('Failed to load prefilled players')
            } finally {
                setPrefilling(false)
            }
        }
        prefill()
    }, []) // eslint-disable-line react-hooks/exhaustive-deps

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

            {prefilling && (
                <div className="comparison-prefill-status">Loading players from roster...</div>
            )}

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
                    onClick={() => runComparison()}
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
