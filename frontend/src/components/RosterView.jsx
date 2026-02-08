import { useState, useEffect, useCallback } from 'react'
import PulseButton from './PulseButton'
import { apiFetch } from '../api/client'
import './RosterView.css'

const DEFAULT_PREFERENCES = {
  scoring: 'ppr',
  risk: 'balanced',
  focus: 'upside',
}

function RosterView() {
  const [teams, setTeams] = useState([])
  const [selectedTeamKey, setSelectedTeamKey] = useState('')
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES)
  const [insights, setInsights] = useState(null)

  const [loadingTeams, setLoadingTeams] = useState(true)
  const [loadingInsights, setLoadingInsights] = useState(false)
  const [savingPreferences, setSavingPreferences] = useState(false)
  const [error, setError] = useState(null)

  const selectedTeam = teams.find(team => team.team_key === selectedTeamKey) || null

  const fetchPreferences = useCallback(async (teamKey) => {
    const response = await apiFetch(`/api/yahoo/teams/${encodeURIComponent(teamKey)}/preferences`)
    if (!response.ok) {
      throw new Error('Failed to fetch team preferences')
    }
    return response.json()
  }, [])

  const fetchInsights = useCallback(async (teamKey, teamPreferences, refresh = false) => {
    const params = new URLSearchParams({
      scoring: teamPreferences.scoring,
      risk: teamPreferences.risk,
      focus: teamPreferences.focus,
      refresh: refresh ? 'true' : 'false',
    })

    setLoadingInsights(true)
    setError(null)

    try {
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
    } finally {
      setLoadingInsights(false)
    }
  }, [])

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
  }, [loadTeamData])

  useEffect(() => {
    fetchTeams()
  }, [fetchTeams])

  const handleTeamChange = async (e) => {
    const teamKey = e.target.value
    setSelectedTeamKey(teamKey)

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
    setError(null)

    try {
      const response = await apiFetch(
        `/api/yahoo/teams/${encodeURIComponent(selectedTeamKey)}/insights/refresh`,
        {
          method: 'POST',
        }
      )

      if (!response.ok) {
        throw new Error('Failed to refresh roster insights')
      }

      const data = await response.json()
      setInsights(data)
      setPreferences(data.preferences || preferences)
    } catch (err) {
      console.error(err)
      setError(err.message)
    }
  }

  if (loadingTeams) {
    return <div className="roster-loading">Loading Yahoo team import...</div>
  }

  if (error) {
    return <div className="roster-error">{error}</div>
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

        {selectedTeam && (
          <div className="team-info">
            <span className="team-name">{selectedTeam.team_name}</span>
            {selectedTeam.season && (
              <span className="team-season">Season {selectedTeam.season}</span>
            )}
          </div>
        )}
      </header>

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
          <span className={`cache-pill ${insights.cached ? 'cached' : 'fresh'}`}>
            {insights.cached ? 'Cached' : 'Fresh'}
          </span>
        </div>
      )}

      <div className="roster-grid">
        {insights?.players?.map(player => {
          const matched = Boolean(player.enhanced_player && player.matched_sleeper_id)
          const projectionValue = matched
            ? player.enhanced_player.projection.adjusted_projection
                ?? player.enhanced_player.projection.sleeper_projection
            : null

          return (
            <div key={player.yahoo_player_key || player.name} className="roster-player-card">
              <div className="player-header">
                <span className="player-pos">{player.position || 'N/A'}</span>
                <span className="player-team">{player.team || 'FA'}</span>
              </div>

              <h3 className="player-name">{player.name}</h3>

              <div className={`match-pill ${matched ? 'matched' : 'unmatched'}`}>
                {matched ? 'Matched to Sleeper' : 'Unmatched'}
              </div>

              <p className="feedback-text">{player.custom_feedback}</p>

              {player.feedback_score !== null && player.feedback_score !== undefined && (
                <div className="feedback-score">Feedback Score: {player.feedback_score.toFixed(1)}</div>
              )}

              {matched && (
                <div className="projection-row">
                  <span className="projection-label">Projection</span>
                  <span className="projection-value">{projectionValue?.toFixed(1)} pts</span>
                </div>
              )}

              {matched && player.enhanced_player.performance_flags?.length > 0 && (
                <div className="flags-inline">
                  {player.enhanced_player.performance_flags.slice(0, 3).map(flag => (
                    <span key={`${player.yahoo_player_key}-${flag}`} className="flag-chip-mini">
                      {flag.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              )}

              {!matched && (
                <p className="match-reason">Reason: {player.match_reason}</p>
              )}

              {player.status && <span className="status-tag">{player.status}</span>}
              {player.injury_status && <span className="injury-tag">{player.injury_status}</span>}

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
