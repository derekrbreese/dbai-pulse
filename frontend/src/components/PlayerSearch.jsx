import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../api/client'
import PlayerHeadshot from './PlayerHeadshot'
import './PlayerSearch.css'

function PlayerSearch({ onPlayerSelect, variant = 'default' }) {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [loading, setLoading] = useState(false)
    const [showDropdown, setShowDropdown] = useState(false)
    const [highlightIndex, setHighlightIndex] = useState(-1)
    const debounceRef = useRef(null)
    const wrapperRef = useRef(null)
    const inputRef = useRef(null)

    // Handle click outside to close dropdown
    useEffect(() => {
        function handleClickOutside(event) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
                setShowDropdown(false)
                setHighlightIndex(-1)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    // Global "/" shortcut to focus search
    useEffect(() => {
        function handleGlobalKey(e) {
            if (e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey) {
                const tag = document.activeElement?.tagName
                if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return
                e.preventDefault()
                inputRef.current?.focus()
            }
        }
        document.addEventListener('keydown', handleGlobalKey)
        return () => document.removeEventListener('keydown', handleGlobalKey)
    }, [])

    // Debounced search
    const searchPlayers = useCallback(async (searchQuery) => {
        if (searchQuery.length < 2) {
            setResults([])
            return
        }

        setLoading(true)
        try {
            const response = await apiFetch(
                `/api/players/search?q=${encodeURIComponent(searchQuery)}&limit=8`
            )
            if (response.ok) {
                const data = await response.json()
                setResults(data)
                setShowDropdown(true)
                setHighlightIndex(-1)
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
        setHighlightIndex(-1)
        onPlayerSelect(player)
    }

    // Keyboard navigation
    const handleKeyDown = (e) => {
        if (!showDropdown || results.length === 0) {
            if (e.key === 'Escape') {
                inputRef.current?.blur()
            }
            return
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault()
                setHighlightIndex(prev =>
                    prev < results.length - 1 ? prev + 1 : 0
                )
                break
            case 'ArrowUp':
                e.preventDefault()
                setHighlightIndex(prev =>
                    prev > 0 ? prev - 1 : results.length - 1
                )
                break
            case 'Enter':
                e.preventDefault()
                if (highlightIndex >= 0 && highlightIndex < results.length) {
                    handleSelect(results[highlightIndex])
                }
                break
            case 'Escape':
                setShowDropdown(false)
                setHighlightIndex(-1)
                inputRef.current?.blur()
                break
        }
    }

    const isHero = variant === 'hero'

    return (
        <div className={`player-search ${isHero ? 'hero' : ''}`} ref={wrapperRef}>
            <div className="search-input-wrapper">
                <span className="search-icon">🔍</span>
                <input
                    ref={inputRef}
                    type="text"
                    value={query}
                    onChange={handleInputChange}
                    onFocus={() => results.length > 0 && setShowDropdown(true)}
                    onKeyDown={handleKeyDown}
                    placeholder={isHero ? 'Search any NFL player...' : 'Search players...'}
                    className={`search-input ${isHero ? 'hero' : ''}`}
                />
                {loading && <span className="search-spinner">⏳</span>}
            </div>

            {showDropdown && results.length > 0 && (
                <ul className="search-results" role="listbox">
                    {results.map((player, index) => (
                        <li
                            key={player.sleeper_id}
                            className={`search-result-item ${index === highlightIndex ? 'highlighted' : ''}`}
                            onClick={() => handleSelect(player)}
                            onMouseEnter={() => setHighlightIndex(index)}
                            role="option"
                            aria-selected={index === highlightIndex}
                        >
                            <PlayerHeadshot espnId={player.espn_id} position={player.position} size={28} />
                            <span className="search-player-name">{player.name}</span>
                            <span className="search-player-team">{player.team || 'FA'}</span>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    )
}

export default PlayerSearch
