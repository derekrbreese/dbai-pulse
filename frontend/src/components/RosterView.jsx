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
                <div className={`roster-match-pill ${matched ? 'matched' : 'unmatched'}`}>
                  {matched ? 'Matched to Sleeper' : 'Unmatched'}
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
                <p className="roster-match-reason">Reason: {player.match_reason}</p>
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
