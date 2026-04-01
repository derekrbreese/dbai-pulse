import { useState, useEffect, useCallback } from 'react'
import PulseButton from './PulseButton'
import PlayerHeadshot from './PlayerHeadshot'
import ScoreBreakdown from './ScoreBreakdown'
import { apiFetch } from '../api/client'
import { RosterGridSkeleton } from './SkeletonLoader'
import useAsyncRequest from '../hooks/useAsyncRequest'
import './RosterView.css'

const DEFAULT_PREFERENCES = {
  scoring: 'ppr',
  risk: 'balanced',
  focus: 'upside',
}

function RosterView({ onPlayerSelect, navigate }) {
  const [teams, setTeams] = useState([])
  const [selectedTeamKey, setSelectedTeamKey] = useState('')
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES)
  const [insights, setInsights] = useState(null)

  const [compareMode, setCompareMode] = useState(false)
  const [compareA, setCompareA] = useState(null)
  const [matchingPlayer, setMatchingPlayer] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [matchSaving, setMatchSaving] = useState(null)

  const [loadingTeams, setLoadingTeams] = useState(true)
  const [savingPreferences, setSavingPreferences] = useState(false)
  const { execute: executeInsights, loading: loadingInsights, error, setError } = useAsyncRequest()

  const selectedTeam = teams.find(team => team.team_key === selectedTeamKey) || null

  const fetchPreferences = useCallback(async (teamKey) => {
    const response = await apiFetch(`/api/yahoo/teams/${encodeURIComponent(teamKey)}/preferences`)
    if (!response.ok) {
      throw new Error('Failed to fetch team preferences')
    }
    return response.json()
  }, [])

  const fetchInsights = useCallback(async (teamKey, teamPreferences, refresh = false) => {
    return executeInsights(async () => {
      const params = new URLSearchParams({
        scoring: teamPreferences.scoring,
        risk: teamPreferences.risk,
        focus: teamPreferences.focus,
        refresh: refresh ? 'true' : 'false',
      })

      const response = await apiFetch(
        `/api/yahoo/teams/${encodeURIComponent(teamKey)}/insights?${params.toString()}`
      )

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Not connected to Yahoo')
        }
        throw new Error('Failed to fetch roster insights')
      }

      const data = await response.json()
      setInsights(data)
      return data
    })
  }, [executeInsights])

  const loadTeamData = useCallback(async (teamKey, refresh = false) => {
    const teamPreferences = await fetchPreferences(teamKey)
    setPreferences(teamPreferences)
    await fetchInsights(teamKey, teamPreferences, refresh)
  }, [fetchPreferences, fetchInsights])

  const fetchTeams = useCallback(async () => {
    setLoadingTeams(true)
    setError(null)

    try {
      const response = await apiFetch('/api/yahoo/teams')
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Not connected to Yahoo')
        }
        throw new Error('Failed to fetch Yahoo teams')
      }

      const data = await response.json()
      const fetchedTeams = data.teams || []

      if (!fetchedTeams.length) {
        setTeams([])
        setSelectedTeamKey('')
        setInsights(null)
        throw new Error('No Yahoo teams found')
      }

      setTeams(fetchedTeams)
      const firstTeamKey = fetchedTeams[0].team_key
      setSelectedTeamKey(firstTeamKey)
      await loadTeamData(firstTeamKey)
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setLoadingTeams(false)
    }
  }, [loadTeamData, setError])

  useEffect(() => {
    fetchTeams()
  }, [fetchTeams])

  const handleTeamChange = async (e) => {
    const teamKey = e.target.value
    setSelectedTeamKey(teamKey)
    setError(null)

    try {
      await loadTeamData(teamKey)
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  const handlePreferenceChange = (field, value) => {
    setPreferences(prev => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleApplyPreferences = async () => {
    if (!selectedTeamKey) return
    setSavingPreferences(true)
    setError(null)

    try {
      const response = await apiFetch(
        `/api/yahoo/teams/${encodeURIComponent(selectedTeamKey)}/preferences`,
        {
          method: 'PUT',
          body: JSON.stringify({
            scoring: preferences.scoring,
            risk: preferences.risk,
            focus: preferences.focus,
          }),
        }
      )

      if (!response.ok) {
        throw new Error('Failed to save preferences')
      }

      const saved = await response.json()
      setPreferences(saved)
      await fetchInsights(selectedTeamKey, saved, true)
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setSavingPreferences(false)
    }
  }

  const handleRefresh = async () => {
    if (!selectedTeamKey) return

    try {
      await executeInsights(async () => {
        const response = await apiFetch(
          `/api/yahoo/teams/${encodeURIComponent(selectedTeamKey)}/insights/refresh`,
          { method: 'POST' }
        )

        if (!response.ok) {
          throw new Error('Failed to refresh roster insights')
        }

        const data = await response.json()
        setInsights(data)
        setPreferences(prev => data.preferences || prev)
        return data
      })
    } catch (err) {
      console.error(err)
    }
  }

  const handleManualMatch = async (player, sleeperId) => {
    if (!selectedTeamKey || matchSaving) return
    setMatchSaving(sleeperId)

    try {
      const yahooPlayerId = player.yahoo_player_key?.includes('.p.')
        ? player.yahoo_player_key.split('.p.').pop()
        : null

      const response = await apiFetch(
        `/api/yahoo/teams/${encodeURIComponent(selectedTeamKey)}/match`,
        {
          method: 'POST',
          body: JSON.stringify({
            yahoo_player_key: player.yahoo_player_key,
            yahoo_player_id: yahooPlayerId,
            sleeper_id: sleeperId,
          }),
        }
      )

      if (!response.ok) throw new Error('Failed to save match')
      const data = await response.json()

      setInsights(prev => {
        if (!prev) return prev
        return {
          ...prev,
          players: prev.players.map(p =>
            p.yahoo_player_key === player.yahoo_player_key
              ? {
                  ...p,
                  matched_sleeper_id: data.matched_sleeper_id,
                  match_confidence: data.match_confidence,
                  match_reason: data.match_reason,
                  enhanced_player: data.enhanced_player,
                  near_matches: [],
                }
              : p
          ),
          matched_count: prev.matched_count + 1,
          unmatched_count: Math.max(prev.unmatched_count - 1, 0),
        }
      })
      setMatchingPlayer(null)
      setSearchQuery('')
      setSearchResults([])
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setMatchSaving(null)
    }
  }

  const handleUnmatch = async (player) => {
    if (!selectedTeamKey) return

    const yahooPlayerId = player.yahoo_player_key?.includes('.p.')
      ? player.yahoo_player_key.split('.p.').pop()
      : null

    try {
      const response = await apiFetch(
        `/api/yahoo/teams/${encodeURIComponent(selectedTeamKey)}/match`,
        {
          method: 'DELETE',
          body: JSON.stringify({
            yahoo_player_key: player.yahoo_player_key,
            yahoo_player_id: yahooPlayerId,
          }),
        }
      )

      if (!response.ok) throw new Error('Failed to unlink match')

      setInsights(prev => {
        if (!prev) return prev
        return {
          ...prev,
          players: prev.players.map(p =>
            p.yahoo_player_key === player.yahoo_player_key
              ? {
                  ...p,
                  matched_sleeper_id: null,
                  match_confidence: null,
                  match_reason: 'unlinked by user',
                  enhanced_player: null,
                  near_matches: [],
                  feedback_score: null,
                  score_breakdown: null,
                  custom_feedback: 'Match removed. Use suggestions or search to re-link.',
                }
              : p
          ),
          matched_count: Math.max(prev.matched_count - 1, 0),
          unmatched_count: prev.unmatched_count + 1,
        }
      })
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  const handlePlayerSearch = async (query) => {
    setSearchQuery(query)
    if (query.length < 2) {
      setSearchResults([])
      return
    }
    setSearchLoading(true)
    try {
      const response = await apiFetch(
        `/api/players/search?q=${encodeURIComponent(query)}&limit=8`
      )
      if (response.ok) {
        setSearchResults(await response.json())
      }
    } catch {
      // silent — search is best-effort
    } finally {
      setSearchLoading(false)
    }
  }

  if (loadingTeams) {
    return (
      <div className="roster-view">
        <div className="roster-loading-header">Loading Yahoo team import...</div>
        <RosterGridSkeleton count={6} />
      </div>
    )
  }

  if (!teams.length) {
    return (
      <div className="roster-empty-state">
        <p className="roster-error">{error || 'No Yahoo teams found for this account.'}</p>
        <button
          type="button"
          className="roster-retry-button"
          onClick={fetchTeams}
        >
          Retry Import
        </button>
      </div>
    )
  }

  return (
    <div className="roster-view">
      <header className="roster-header">
        <div className="league-selector">
          <label htmlFor="team-select">Team:</label>
          <select
            id="team-select"
            value={selectedTeamKey}
            onChange={handleTeamChange}
          >
            {teams.map(team => (
              <option key={team.team_key} value={team.team_key}>
                {team.team_name} • {team.league_name || team.league_key}
              </option>
            ))}
          </select>
        </div>

        <div className="roster-header-actions">
          {selectedTeam && (
            <div className="team-info">
              <span className="team-name">{selectedTeam.team_name}</span>
              {selectedTeam.season && (
                <span className="team-season">Season {selectedTeam.season}</span>
              )}
            </div>
          )}

          <button
            type="button"
            className={`compare-toggle${compareMode ? ' active' : ''}`}
            onClick={() => {
              setCompareMode(prev => !prev)
              setCompareA(null)
            }}
          >
            {compareMode ? 'Exit Compare' : 'Compare'}
          </button>
        </div>
      </header>

      {compareMode && (
        <div className="compare-banner">
          <span>
            {compareA
              ? `Player A selected — now pick Player B`
              : 'Select 2 matched players to compare'}
          </span>
          <button
            type="button"
            onClick={() => {
              setCompareMode(false)
              setCompareA(null)
            }}
          >
            Cancel
          </button>
        </div>
      )}

      {error && (
        <div className="roster-inline-error">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
          >
            Dismiss
          </button>
        </div>
      )}

      <section className="feedback-controls">
        <div className="control-group">
          <label htmlFor="scoring-select">Scoring</label>
          <select
            id="scoring-select"
            value={preferences.scoring}
            onChange={(e) => handlePreferenceChange('scoring', e.target.value)}
          >
            <option value="ppr">PPR</option>
            <option value="half_ppr">Half PPR</option>
            <option value="std">Standard</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="risk-select">Risk</label>
          <select
            id="risk-select"
            value={preferences.risk}
            onChange={(e) => handlePreferenceChange('risk', e.target.value)}
          >
            <option value="conservative">Conservative</option>
            <option value="balanced">Balanced</option>
            <option value="aggressive">Aggressive</option>
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="focus-select">Focus</label>
          <select
            id="focus-select"
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
            disabled={savingPreferences || loadingInsights}
          >
            {savingPreferences ? 'Saving...' : 'Apply Feedback Settings'}
          </button>

          <button
            type="button"
            className="refresh-button"
            onClick={handleRefresh}
            disabled={loadingInsights || savingPreferences}
          >
            {loadingInsights ? 'Refreshing...' : 'Refresh Import'}
          </button>
        </div>
      </section>

      {insights && (
        <div className="insights-summary">
          <span>{insights.summary}</span>
          <div className="insights-status">
            {loadingInsights && (
              <span className="cache-pill updating">Updating...</span>
            )}
            <span className={`cache-pill ${insights.cached ? 'cached' : 'fresh'}`}>
              {insights.cached ? 'Cached' : 'Fresh'}
            </span>
          </div>
        </div>
      )}

      {loadingInsights && !insights && <RosterGridSkeleton count={8} />}

      <div className="roster-grid">
        {insights?.players?.map(player => {
          const matched = Boolean(player.enhanced_player && player.matched_sleeper_id)
          const projectionValue = matched
            ? player.enhanced_player.projection.adjusted_projection
                ?? player.enhanced_player.projection.sleeper_projection
            : null

          const isCompareA = compareMode && matched && compareA === player.matched_sleeper_id
          const compareSelectable = compareMode && matched

          return (
            <div
              key={player.yahoo_player_key || player.name}
              className={[
                'roster-player-card',
                matched ? 'clickable' : '',
                compareSelectable ? 'compare-selectable' : '',
                isCompareA ? 'compare-selected' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => {
                if (!matched) return
                if (compareMode) {
                  if (!compareA) {
                    setCompareA(player.matched_sleeper_id)
                  } else if (compareA !== player.matched_sleeper_id) {
                    navigate(`compare?a=${compareA}&b=${player.matched_sleeper_id}`)
                    setCompareMode(false)
                    setCompareA(null)
                  }
                  return
                }
                if (onPlayerSelect) {
                  onPlayerSelect(player.enhanced_player.player)
                }
              }}
              style={matched ? { cursor: 'pointer' } : undefined}
            >
              <div className="roster-player-header">
                <PlayerHeadshot
                  espnId={player.enhanced_player?.player?.espn_id}
                  position={player.position || 'N/A'}
                  size={32}
                />
                <span className="roster-player-team">{player.team || 'FA'}</span>
                {isCompareA && <span className="compare-a-badge">A</span>}
              </div>

              <h3 className="roster-player-name">{player.name}</h3>

              <div className="roster-badge-row">
                <div className="roster-match-pill-group">
                  <div className={`roster-match-pill ${
                    !matched ? 'unmatched'
                    : player.match_reason === 'manual match' ? 'linked'
                    : player.match_confidence >= 0.95 ? 'matched'
                    : 'auto-matched'
                  }`}>
                    {!matched ? 'Unmatched'
                     : player.match_reason === 'manual match' ? 'Linked'
                     : player.match_confidence >= 0.95 ? 'Matched'
                     : 'Auto-matched'}
                  </div>
                  {matched && (
                    <button
                      className="unlink-button"
                      title="Remove this match"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleUnmatch(player)
                      }}
                    >
                      Unlink
                    </button>
                  )}
                </div>

                {player.feedback_score != null && (
                  <ScoreBreakdown score={player.feedback_score} breakdown={player.score_breakdown} />
                )}
              </div>

              <p className="roster-feedback-label">Feedback</p>
              <p className="roster-feedback-text">{player.custom_feedback}</p>

              {matched && (
                <div className="roster-analytics">
                  <div className="roster-projection-row">
                    <span className="roster-projection-label">Projection</span>
                    <span className="roster-projection-value">{projectionValue?.toFixed(1)} pts</span>
                  </div>

                  {player.enhanced_player.performance_flags?.length > 0 && (
                    <div className="roster-flags-inline">
                      {player.enhanced_player.performance_flags.slice(0, 3).map(flag => (
                        <span key={`${player.yahoo_player_key}-${flag}`} className="roster-flag-chip">
                          {flag.replace(/_/g, ' ')}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {!matched && (
                <div className="roster-match-actions">
                  {player.near_matches?.length > 0 && (
                    <div className="near-match-suggestions">
                      <span className="near-match-label">Did you mean?</span>
                      <div className="near-match-chips">
                        {player.near_matches.map(nm => (
                          <button
                            key={nm.sleeper_id}
                            className="near-match-chip"
                            disabled={matchSaving === nm.sleeper_id}
                            onClick={(e) => {
                              e.stopPropagation()
                              handleManualMatch(player, nm.sleeper_id)
                            }}
                          >
                            <span className="nm-name">{nm.name}</span>
                            <span className="nm-meta">{nm.position} {nm.team || ''}</span>
                            {matchSaving === nm.sleeper_id && <span className="nm-saving">saving...</span>}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {matchingPlayer === player.yahoo_player_key ? (
                    <div className="match-search-inline">
                      <input
                        type="text"
                        className="match-search-input"
                        placeholder="Search Sleeper players..."
                        value={searchQuery}
                        onChange={(e) => handlePlayerSearch(e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                      />
                      {searchResults.length > 0 && (
                        <div className="match-search-results">
                          {searchResults.map(r => (
                            <button
                              key={r.sleeper_id}
                              className="match-search-result"
                              disabled={matchSaving === r.sleeper_id}
                              onClick={(e) => {
                                e.stopPropagation()
                                handleManualMatch(player, r.sleeper_id)
                              }}
                            >
                              {r.name} — {r.position} {r.team || ''}
                            </button>
                          ))}
                        </div>
                      )}
                      {searchLoading && <span className="match-search-loading">Searching...</span>}
                      <button
                        className="match-search-cancel"
                        onClick={(e) => {
                          e.stopPropagation()
                          setMatchingPlayer(null)
                          setSearchQuery('')
                          setSearchResults([])
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      className="match-search-trigger"
                      onClick={(e) => {
                        e.stopPropagation()
                        setMatchingPlayer(player.yahoo_player_key)
                      }}
                    >
                      Search all players
                    </button>
                  )}

                  <span className="roster-match-reason-small">{player.match_reason}</span>
                </div>
              )}

              {(player.status || player.injury_status) && (
                <div className="roster-chip-row">
                  {player.status && <span className="roster-status-tag">{player.status}</span>}
                  {player.injury_status && (
                    <span className={`injury-badge ${player.injury_status.toLowerCase().replace('_', '')}`}>
                      {player.injury_status}
                    </span>
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
        })}
      </div>
    </div>
  )
}

export default RosterView
