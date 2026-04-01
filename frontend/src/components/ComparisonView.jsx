import { useState, useEffect, useRef } from 'react'
import { apiFetch } from '../api/client'
import PlayerSlot from './PlayerSlot'
import ComparisonResult from './ComparisonResult'
import './ComparisonView.css'

const SUGGESTED_MATCHUPS = [
    {
        label: 'QB Battle',
        playerA: { sleeper_id: '6744', name: 'Josh Allen' },
        playerB: { sleeper_id: '4881', name: 'Lamar Jackson' },
    },
    {
        label: 'RB Showdown',
        playerA: { sleeper_id: '4866', name: 'Saquon Barkley' },
        playerB: { sleeper_id: '4018', name: 'Derrick Henry' },
    },
    {
        label: 'WR Duel',
        playerA: { sleeper_id: '7564', name: "Ja'Marr Chase" },
        playerB: { sleeper_id: '6786', name: 'CeeDee Lamb' },
    },
    {
        label: 'TE Clash',
        playerA: { sleeper_id: '4993', name: 'Sam LaPorta' },
        playerB: { sleeper_id: '4988', name: 'Trey McBride' },
    },
]

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

            {/* Suggested Matchups — show when empty */}
            {!playerA && !playerB && !result && !loading && (
                <div className="suggested-matchups">
                    <h3 className="suggested-title">🔥 Popular Comparisons</h3>
                    <p className="suggested-subtitle">Click one to run an instant AI head-to-head</p>
                    <div className="suggested-grid">
                        {SUGGESTED_MATCHUPS.map((matchup) => (
                            <button
                                key={matchup.label}
                                className="suggested-chip"
                                onClick={async () => {
                                    setPlayerA(matchup.playerA)
                                    setPlayerB(matchup.playerB)
                                    await runComparison(matchup.playerA, matchup.playerB)
                                }}
                            >
                                <span className="suggested-chip-label">{matchup.label}</span>
                                <span className="suggested-chip-players">
                                    {matchup.playerA.name} vs {matchup.playerB.name}
                                </span>
                            </button>
                        ))}
                    </div>
                </div>
            )}

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
