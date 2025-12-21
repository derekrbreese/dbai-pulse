import { useState, useCallback } from 'react'
import PlayerSearch from './components/PlayerSearch'
import EnhancedCard from './components/EnhancedCard'
import PerformanceChart from './components/PerformanceChart'
import ComparisonView from './components/ComparisonView'
import FlagsBrowser from './components/FlagsBrowser'
import './App.css'

function App() {
  const [selectedPlayer, setSelectedPlayer] = useState(null)
  const [enhancedData, setEnhancedData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showComparison, setShowComparison] = useState(false)
  const [showFlagsBrowser, setShowFlagsBrowser] = useState(false)

  const handlePlayerSelect = useCallback(async (player) => {
    setSelectedPlayer(player)
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`http://localhost:8000/api/players/${player.sleeper_id}`)
      if (!response.ok) {
        throw new Error('Failed to fetch player data')
      }
      const data = await response.json()
      setEnhancedData(data)
    } catch (err) {
      setError(err.message)
      setEnhancedData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>
          <span className="brand">dbAI</span> Pulse
        </h1>
        <p className="tagline">Fantasy Football Intelligence Dashboard</p>

        <div className="header-buttons">
          {/* Trends & Insights Button */}
          <button
            className="trends-nav-button"
            onClick={() => setShowFlagsBrowser(true)}
          >
            📊 Trends
          </button>

          {/* Compare Button */}
          <button
            className="compare-nav-button"
            onClick={() => setShowComparison(true)}
          >
            🔄 Compare
          </button>
        </div>
      </header>

      <main className="app-main">
        <section className="search-section">
          <PlayerSearch onPlayerSelect={handlePlayerSelect} />
        </section>

        {loading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading player data...</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <p>⚠️ {error}</p>
          </div>
        )}

        {enhancedData && !loading && (
          <section className="player-section">
            <EnhancedCard data={enhancedData} />
            <PerformanceChart
              playerId={selectedPlayer.sleeper_id}
              playerName={selectedPlayer.name}
            />
          </section>
        )}

        {!selectedPlayer && !loading && (
          <div className="empty-state">
            <div className="empty-icon">🏈</div>
            <h2>Search for a player</h2>
            <p>Get enhanced projections, performance flags, and AI-powered insights</p>
          </div>
        )}
      </main>

      <footer className="app-footer">
        <p>dbAI Pulse v0.2.0 • Data from Sleeper API • Powered by Gemini 3 Flash</p>
      </footer>

      {/* Comparison Modal */}
      {showComparison && (
        <ComparisonView onClose={() => setShowComparison(false)} />
      )}

      {/* Flags Browser Modal */}
      {showFlagsBrowser && (
        <FlagsBrowser
          onClose={() => setShowFlagsBrowser(false)}
          onPlayerSelect={handlePlayerSelect}
        />
      )}
    </div>
  )
}

export default App
