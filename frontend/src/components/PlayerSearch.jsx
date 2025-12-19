import { useState, useEffect, useCallback, useRef } from 'react'
import './PlayerSearch.css'

function PlayerSearch({ onPlayerSelect }) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [loading, setLoading] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const debounceRef = useRef(null)
    const wrapperRef = useRef(null)

    // Handle click outside to close dropdown
    useEffect(() => {
        function handleClickOutside(event) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setShowDropdown(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    // Debounced search
    const searchPlayers = useCallback(async (searchQuery) => {
        if (searchQuery.length < 2) {
            setResults([])
            return
        }

        setLoading(true)
        try {
            const response = await fetch(
                `http://localhost:8000/api/players/search?q=${encodeURIComponent(searchQuery)}&limit=8`
            )
            if (response.ok) {
                const data = await response.json()
                setResults(data)
                setShowDropdown(true)
            }
        } catch (err) {
            console.error('Search failed:', err)
            setResults([])
        } finally {
            setLoading(false)
        }
    }, [])

    // Handle input change with debounce
    const handleInputChange = (e) => {
        const value = e.target.value
        setQuery(value)

        if (debounceRef.current) {
            clearTimeout(debounceRef.current)
        }

        debounceRef.current = setTimeout(() => {
            searchPlayers(value)
        }, 300)
    }

    // Handle player selection
    const handleSelect = (player) => {
        setQuery(player.name)
        setShowDropdown(false)
        onPlayerSelect(player)
    }

    // Get position badge color
    const getPositionColor = (position) => {
        const colors = {
            QB: '#e74c3c',
            RB: '#27ae60',
            WR: '#3498db',
            TE: '#f39c12',
            K: '#9b59b6',
            DEF: '#34495e',
        }
        return colors[position] || '#7f8c8d'
    }

    return (
        <div className="player-search" ref={wrapperRef}>
            <div className="search-input-wrapper">
                <span className="search-icon">🔍</span>
                <input
                    type="text"
                    value={query}
                    onChange={handleInputChange}
                    onFocus={() => results.length > 0 && setShowDropdown(true)}
                    placeholder="Search players..."
                    className="search-input"
                />
                {loading && <span className="search-spinner">⏳</span>}
            </div>

            {showDropdown && results.length > 0 && (
                <ul className="search-results">
                    {results.map((player) => (
                        <li
                            key={player.sleeper_id}
                            className="search-result-item"
                            onClick={() => handleSelect(player)}
                        >
                            <span
                                className="position-badge"
                                style={{ backgroundColor: getPositionColor(player.position) }}
                            >
                                {player.position}
                            </span>
                            <span className="player-name">{player.name}</span>
                            <span className="player-team">{player.team || 'FA'}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}

export default PlayerSearch
