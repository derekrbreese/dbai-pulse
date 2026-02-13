import { useState, useEffect, useCallback, useRef } from 'react'
import PulseButton from './PulseButton'
import PlayerHeadshot from './PlayerHeadshot'
import { apiFetch } from '../api/client'
import './WaiverWire.css'

const POSITION_FILTERS = ['All', 'QB', 'RB', 'WR', 'TE', 'K', 'DEF']

const RECOMMENDATION_FILTERS = ['All', 'GRAB', 'WATCH', 'SKIP']

const TIER_CONFIG = {
  GRAB:  { emoji: '\u{1F7E2}', label: 'Recommended Pickups', accent: 'rgba(34, 197, 94, 0.6)' },
  WATCH: { emoji: '\u{1F7E1}', label: 'Monitor',             accent: 'rgba(245, 158, 11, 0.6)' },
  SKIP:  { emoji: '\u26AA',    label: 'Low Priority',         accent: 'rgba(148, 163, 184, 0.4)' },
}

const DEFAULT_PREFERENCES = {
  scoring: 'ppr',
  risk: 'balanced',
  focus: 'upside',
}

function WaiverWire({ onPlayerSelect, navigate }) {
  const [teams, setTeams] = useState([])
  const [leagues, setLeagues] = useState([])
  const [selectedLeagueKey, setSelectedLeagueKey] = useState('')
  const [positionFilter, setPositionFilter] = useState('All')
  const [recommendationFilter, setRecommendationFilter] = useState('All')
  const [collapsedTiers, setCollapsedTiers] = useState({ SKIP: true })
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES)
  const [waiverData, setWaiverData] = useState(null)

  const [loadingTeams, setLoadingTeams] = useState(true)
  const [loadingWaivers, setLoadingWaivers] = useState(false)
  const [error, setError] = useState(null)
  const activeRequestRef = useRef(0)

  const nextRequestToken = () => {
    activeRequestRef.current += 1
    return activeRequestRef.current
  }
  const isActiveRequest = (token) => token === activeRequestRef.current

  // Derive unique leagues from teams
  const deriveLeagues = useCallback((teamsList) => {
    const seen = new Map()
    for (const team of teamsList) {
      const lk = team.league_key
      if (lk && !seen.has(lk)) {
        seen.set(lk, {
          league_key: lk,
          league_name: team.league_name || lk,
          season: team.season,
        })
      }
    }
    return Array.from(seen.values())
  }, [])

  const fetchWaivers = useCallback(async (leagueKey, pos, prefs, requestToken) => {
    const token = requestToken ?? nextRequestToken()
    setLoadingWaivers(true)
    setError(null)

    const params = new URLSearchParams({
      scoring: prefs.scoring,
      risk: prefs.risk,
      focus: prefs.focus,
    })
    if (pos && pos !== 'All') {
      params.set('position', pos)
    }

    try {
      const response = await apiFetch(
        `/api/yahoo/leagues/${encodeURIComponent(leagueKey)}/waivers?${params.toString()}`
      )
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Not connected to Yahoo')
        }
        throw new Error('Failed to fetch waiver wire data')
      }

      const data = await response.json()
      if (!isActiveRequest(token)) return null
      setWaiverData(data)
      return data
    } catch (err) {
      if (isActiveRequest(token)) throw err
      return null
    } finally {
      if (isActiveRequest(token)) setLoadingWaivers(false)
    }
  }, [])

  const fetchTeams = useCallback(async () => {
    setLoadingTeams(true)
    setError(null)

    try {
      const response = await apiFetch('/api/yahoo/teams')
      if (!response.ok) {
        if (response.status === 401) throw new Error('Not connected to Yahoo')
        throw new Error('Failed to fetch Yahoo teams')
      }

      const data = await response.json()
      const fetchedTeams = data.teams || []

      if (!fetchedTeams.length) {
        setTeams([])
        setLeagues([])
        throw new Error('No Yahoo teams found')
      }

      setTeams(fetchedTeams)
      const derived = deriveLeagues(fetchedTeams)
      setLeagues(derived)

      if (derived.length) {
        const firstKey = derived[0].league_key
        setSelectedLeagueKey(firstKey)
        await fetchWaivers(firstKey, 'All', DEFAULT_PREFERENCES, nextRequestToken())
      }
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setLoadingTeams(false)
    }
  }, [deriveLeagues, fetchWaivers])

  useEffect(() => {
    fetchTeams()
  }, [fetchTeams])

  const handleLeagueChange = async (e) => {
    const leagueKey = e.target.value
    setSelectedLeagueKey(leagueKey)
    setPositionFilter('All')
    setRecommendationFilter('All')
    setWaiverData(null)
    setError(null)

    try {
      await fetchWaivers(leagueKey, 'All', preferences, nextRequestToken())
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  const handlePositionChange = async (pos) => {
    setPositionFilter(pos)
    if (!selectedLeagueKey) return

    try {
      await fetchWaivers(selectedLeagueKey, pos, preferences, nextRequestToken())
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  const handlePreferenceChange = (field, value) => {
    setPreferences(prev => ({ ...prev, [field]: value }))
  }

  const handleApplyPreferences = async () => {
    if (!selectedLeagueKey) return
    setError(null)
    try {
      await fetchWaivers(selectedLeagueKey, positionFilter, preferences, nextRequestToken())
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  if (loadingTeams) {
    return <div className="waiver-loading">Loading Yahoo leagues...</div>
  }

  if (!leagues.length) {
    return (
      <div className="waiver-empty-state">
        <p className="waiver-error">{error || 'No Yahoo leagues found for this account.'}</p>
        <button type="button" className="waiver-retry-button" onClick={fetchTeams}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="waiver-view">
      <header className="waiver-header">
        <div className="waiver-title-row">
          <div className="waiver-title">
            <span className="waiver-icon">📋</span>
            <div>
              <h2>Waiver Wire</h2>
              <p className="waiver-subtitle">Find available players worth picking up</p>
            </div>
          </div>
        </div>

        <div className="league-selector">
          <label htmlFor="waiver-league-select">League:</label>
          <select
            id="waiver-league-select"
            value={selectedLeagueKey}
            onChange={handleLeagueChange}
          >
            {leagues.map(league => (
              <option key={league.league_key} value={league.league_key}>
                {league.league_name}{league.season ? ` (${league.season})` : ''}
              </option>
            ))}
          </select>
        </div>
      </header>

      {/* Position Filters */}
      <div className="waiver-position-filters">
        {POSITION_FILTERS.map(pos => (
          <button
            key={pos}
            type="button"
            className={`position-filter-tab${positionFilter === pos ? ' active' : ''}`}
            onClick={() => handlePositionChange(pos)}
            disabled={loadingWaivers}
          >
            {pos}
          </button>
        ))}
      </div>

      {/* Recommendation Filters */}
      {waiverData?.players?.length > 0 && (() => {
        const allPlayers = waiverData.players
        const recCounts = { GRAB: 0, WATCH: 0, SKIP: 0 }
        for (const p of allPlayers) recCounts[p.recommendation] = (recCounts[p.recommendation] || 0) + 1
        return (
          <div className="waiver-recommendation-filters">
            {RECOMMENDATION_FILTERS.map(rec => (
              <button
                key={rec}
                type="button"
                className={`recommendation-filter-tab${recommendationFilter === rec ? ' active' : ''}${rec !== 'All' ? ` rec-${rec.toLowerCase()}` : ''}`}
                onClick={() => setRecommendationFilter(rec)}
              >
                {rec}
                {rec !== 'All' && <span className="rec-filter-count">{recCounts[rec] || 0}</span>}
                {rec === 'All' && <span className="rec-filter-count">{allPlayers.length}</span>}
              </button>
            ))}
          </div>
        )
      })()}

      {error && (
        <div className="waiver-inline-error">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* Preference Controls */}
      <section className="feedback-controls waiver-controls">
        <div className="control-group">
          <label htmlFor="w-scoring-select">Scoring</label>
          <select
            id="w-scoring-select"
            value={preferences.scoring}
            onChange={(e) => handlePreferenceChange('scoring', e.target.value)}
          >
            <option value="ppr">PPR</option>
            <option value="half_ppr">Half PPR</option>
            <option value="std">Standard</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="w-risk-select">Risk</label>
          <select
            id="w-risk-select"
            value={preferences.risk}
            onChange={(e) => handlePreferenceChange('risk', e.target.value)}
          >
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="w-focus-select">Focus</label>
          <select
            id="w-focus-select"
            value={preferences.focus}
            onChange={(e) => handlePreferenceChange('focus', e.target.value)}
          >
            <option value="floor">Floor</option>
            <option value="upside">Upside</option>
            <option value="ceiling">Ceiling</option>
          </select>
        </div>

        <div className="control-actions">
          <button
            type="button"
            className="apply-button"
            onClick={handleApplyPreferences}
            disabled={loadingWaivers}
          >
            {loadingWaivers ? 'Loading...' : 'Apply Settings'}
          </button>
        </div>
      </section>

      {/* Summary */}
      {waiverData && (
        <div className="waiver-summary">
          <span>{waiverData.summary}</span>
        </div>
      )}

      {/* Loading state */}
      {loadingWaivers && !waiverData && (
        <div className="waiver-loading">Scanning free agents...</div>
      )}

      {/* Tiered Player Grid */}
      {waiverData && (() => {
        const allPlayers = waiverData.players || []
        const filtered = recommendationFilter === 'All'
          ? allPlayers
          : allPlayers.filter(p => p.recommendation === recommendationFilter)

        const tierGroups = { GRAB: [], WATCH: [], SKIP: [] }
        for (const p of filtered) {
          const bucket = tierGroups[p.recommendation] || tierGroups.SKIP
          bucket.push(p)
        }

        const renderPlayerCard = (player) => {
          const matched = Boolean(player.enhanced_player && player.matched_sleeper_id)
          const projectionValue = matched
            ? player.enhanced_player.projection.adjusted_projection
                ?? player.enhanced_player.projection.sleeper_projection
            : null

          return (
            <div
              key={player.yahoo_player_key || player.name}
              className={`waiver-player-card${matched ? ' clickable' : ''}`}
              onClick={() => {
                if (matched && onPlayerSelect) {
                  onPlayerSelect(player.enhanced_player.player)
                  if (navigate) navigate('search')
                }
              }}
              style={matched ? { cursor: 'pointer' } : undefined}
            >
              <div className="waiver-player-header">
                <PlayerHeadshot
                  espnId={player.enhanced_player?.player?.espn_id}
                  position={player.position || 'N/A'}
                  size={32}
                />
                <span className="waiver-player-team">{player.team || 'FA'}</span>
              </div>

              <h3 className="waiver-player-name">{player.name}</h3>

              <div className="waiver-badge-row">
                <div className={`waiver-recommendation-badge ${player.recommendation.toLowerCase()}`}>
                  {player.recommendation}
                </div>

                {player.percent_owned != null && (
                  <div className="waiver-owned-pill">
                    {player.percent_owned.toFixed(0)}% owned
                  </div>
                )}

                {player.score != null && (
                  <div className="waiver-score">Score {player.score.toFixed(1)}</div>
                )}
              </div>

              <p className="waiver-reasoning">{player.reasoning}</p>

              {matched && (
                <div className="waiver-analytics">
                  <div className="waiver-projection-row">
                    <span className="waiver-projection-label">Projection</span>
                    <span className="waiver-projection-value">{projectionValue?.toFixed(1)} pts</span>
                  </div>

                  {player.enhanced_player.performance_flags?.length > 0 && (
                    <div className="waiver-flags-inline">
                      {player.enhanced_player.performance_flags.slice(0, 3).map(flag => (
                        <span key={`${player.yahoo_player_key}-${flag}`} className="waiver-flag-chip">
                          {flag.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {matched && (
                <div className="pulse-wrapper">
                  <PulseButton
                    sleeperId={player.enhanced_player.player.sleeper_id}
                    playerName={player.enhanced_player.player.name}
                  />
                </div>
              )}
            </div>
          )
        }

        return (
          <div className="waiver-tiered-list">
            {['GRAB', 'WATCH', 'SKIP'].map(tier => {
              const players = tierGroups[tier]
              if (!players.length) return null
              const config = TIER_CONFIG[tier]
              const isCollapsed = collapsedTiers[tier]

              return (
                <div key={tier} className="waiver-tier-section">
                  <button
                    type="button"
                    className="waiver-tier-header"
                    style={{ '--tier-accent': config.accent }}
                    onClick={() => setCollapsedTiers(prev => ({ ...prev, [tier]: !prev[tier] }))}
                  >
                    <span className="waiver-tier-title">
                      {config.emoji} {config.label} ({players.length})
                    </span>
                    <span className={`waiver-tier-chevron${isCollapsed ? ' collapsed' : ''}`}>&#9660;</span>
                  </button>
                  {!isCollapsed && (
                    <div className="waiver-grid">
                      {players.map(renderPlayerCard)}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )
      })()}
    </div>
  )
}

export default WaiverWire
