import { useState, useEffect, useCallback } from 'react'
import EnhancedCard from './EnhancedCard'
import './RosterView.css'

function RosterView() {
  const [leagues, setLeagues] = useState([])
  const [selectedLeague, setSelectedLeague] = useState(null)
  const [userTeam, setUserTeam] = useState(null)
  const [roster, setRoster] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const enhanceRoster = useCallback(async (_rosterData) => {
    // This would fetch Pulse data for each player
    // For now, we just display the basic Yahoo data
    // Future: Match Yahoo player names to Sleeper IDs and call Pulse API
  }, [])

  const fetchRoster = useCallback(async (leagueId, teamId) => {
    try {
      setLoading(true)
      const response = await fetch(`http://localhost:8000/api/yahoo/leagues/${leagueId}/roster/${teamId}`)
      
      if (response.ok) {
        const data = await response.json()
        setRoster(data.roster)
        enhanceRoster(data.roster)
      }
    } catch (err) {
      console.error('Failed to fetch roster:', err)
    } finally {
      setLoading(false)
    }
  }, [enhanceRoster])

  const fetchUserTeam = useCallback(async (leagueKey) => {
    try {
      // Get all user teams to find the one for this league
      const response = await fetch('http://localhost:8000/api/yahoo/teams')
      if (response.ok) {
        const data = await response.json()
        const team = data.teams.find(t => t.league_key === leagueKey)
        if (team) {
          setUserTeam(team)
          fetchRoster(team.league_key.split('.').pop(), team.team_key.split('.').pop())
        }
      }
    } catch (err) {
      console.error('Failed to fetch user team:', err)
    }
  }, [fetchRoster])

  const fetchLeagues = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch('http://localhost:8000/api/yahoo/leagues')
      
      if (!response.ok) {
        if (response.status === 401) {
          setError('Not connected to Yahoo')
        } else {
          throw new Error('Failed to fetch leagues')
        }
        return
      }
      
      const data = await response.json()
      setLeagues(data.leagues)
      
      if (data.leagues.length > 0) {
        // Select first league by default
        const firstLeague = data.leagues[0]
        setSelectedLeague(firstLeague)
        // Also need to find user's team in this league
        fetchUserTeam(firstLeague.league_key)
      } else {
        setError('No leagues found')
      }
    } catch (err) {
      console.error(err)
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [fetchUserTeam])

  // Fetch user leagues on mount
  useEffect(() => {
    fetchLeagues()
  }, [fetchLeagues])

  const handleLeagueChange = (e) => {
    const leagueKey = e.target.value
    const league = leagues.find(l => l.league_key === leagueKey)
    setSelectedLeague(league)
    fetchUserTeam(leagueKey)
  }

  if (loading && !leagues.length) {
    return <div className="roster-loading">Loading Yahoo data...</div>
  }

  if (error) {
    return <div className="roster-error">{error}</div>
  }

  return (
    <div className="roster-view">
      <header className="roster-header">
        <div className="league-selector">
          <label htmlFor="league-select">League:</label>
          <select 
            id="league-select" 
            value={selectedLeague?.league_key || ''} 
            onChange={handleLeagueChange}
          >
            {leagues.map(league => (
              <option key={league.league_key} value={league.league_key}>
                {league.name} ({league.season})
              </option>
            ))}
          </select>
        </div>
        
        {userTeam && (
          <div className="team-info">
            <span className="team-name">{userTeam.name}</span>
          </div>
        )}
      </header>

      <div className="roster-grid">
        {roster.map(player => (
          <div key={player.player_key} className="roster-player-card">
            <div className="player-header">
              <span className="player-pos">{player.position}</span>
              <span className="player-team">{player.team}</span>
            </div>
            <h3 className="player-name">{player.name}</h3>
            <div className="player-status">
              {player.status && <span className="status-tag">{player.status}</span>}
              {player.injury_status && <span className="injury-tag">{player.injury_status}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default RosterView
