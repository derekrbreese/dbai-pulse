import { useState } from 'react'
import './PlayerSlot.css'

function PlayerSlot({ label, player, onSelect }) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [searching, setSearching] = useState(false)

    const searchPlayers = async (q) => {
        if (q.length < 2) {
            setResults([])
            return
        }

        setSearching(true)
        try {
            const response = await fetch(`http://localhost:8000/api/players/search?q=${encodeURIComponent(q)}&limit=5`)
            if (response.ok) {
                const data = await response.json()
                setResults(data)
            }
        } catch (err) {
            console.error('Search error:', err)
        } finally {
            setSearching(false)
        }
    }

    const handleInputChange = (e) => {
        const value = e.target.value
        setQuery(value)
        searchPlayers(value)
    }

    const selectPlayer = (p) => {
        onSelect(p)
        setQuery('')
        setResults([])
    }

    const clearSelection = () => {
        onSelect(null)
    }

    if (player) {
        return (
            <div className="player-slot selected">
                <div className="slot-label">{label}</div>
                <div className="selected-player">
                    <div className="selected-info">
                        <span className={`slot-position position-${player.position?.toLowerCase()}`}>
                            {player.position}
                        </span>
                        <div className="selected-details">
                            <span className="selected-name">{player.name}</span>
                            <span className="selected-team">{player.team || 'FA'}</span>
                        </div>
                    </div>
                    <button className="clear-button" onClick={clearSelection}>✕</button>
                </div>
            </div>
        )
    }

    return (
        <div className="player-slot empty">
            <div className="slot-label">{label}</div>
            <input
                type="text"
                className="slot-search"
                placeholder="Search player..."
                value={query}
                onChange={handleInputChange}
            />
            {searching && <div className="slot-searching">Searching...</div>}
            {results.length > 0 && (
                <div className="slot-results">
                    {results.map((p) => (
                        <div
                            key={p.sleeper_id}
                            className="slot-result"
                            onClick={() => selectPlayer(p)}
                        >
                            <span className={`slot-position position-${p.position.toLowerCase()}`}>
                                {p.position}
                            </span>
                            <span className="result-name">{p.name}</span>
                            <span className="result-team">{p.team || 'FA'}</span>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}

export default PlayerSlot
