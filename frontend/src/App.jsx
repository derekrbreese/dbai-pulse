import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from './api/client'
import PlayerSearch from './components/PlayerSearch'
import EnhancedCard from './components/EnhancedCard'
import PerformanceChart from './components/PerformanceChart'
import ComparisonView from './components/ComparisonView'
import FlagsBrowser from './components/FlagsBrowser'
import AuthPage from './components/AuthPage'
import YahooConnect from './components/YahooConnect'
import RosterView from './components/RosterView'
import YahooSetupPage from './components/YahooSetupPage'
import './App.css'

function App() {
  const [authUser, setAuthUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState(null)
  const [showAuthGate, setShowAuthGate] = useState(false)
  const [authIntent, setAuthIntent] = useState(null)

  const [selectedPlayer, setSelectedPlayer] = useState(null)
  const [enhancedData, setEnhancedData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showComparison, setShowComparison] = useState(false)
  const [showFlagsBrowser, setShowFlagsBrowser] = useState(false)
  const [showRoster, setShowRoster] = useState(false)
  const [showYahooSetup, setShowYahooSetup] = useState(false)

  const loadAuthSession = useCallback(async () => {
    setAuthLoading(true)
    setAuthError(null)

    try {
      const response = await apiFetch('/api/auth/me')
      if (!response.ok) {
        throw new Error('Failed to verify login session')
      }

      const data = await response.json()
      if (data.authenticated && data.user) {
        setAuthUser(data.user)
      } else {
        setAuthUser(null)
      }
    } catch (err) {
      setAuthUser(null)
      setAuthError(err.message)
    } finally {
      setAuthLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAuthSession()
  }, [loadAuthSession])

  const handleAuthenticated = (user) => {
    setAuthUser(user)
    setAuthError(null)
    setShowAuthGate(false)

    if (authIntent === 'yahoo_setup') {
      setShowYahooSetup(true)
      setShowRoster(false)
    }
    setAuthIntent(null)
  }

  const handleLogout = useCallback(async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' })
    } catch (err) {
      console.error('Logout failed:', err)
    } finally {
      setAuthUser(null)
      setShowAuthGate(false)
      setAuthIntent(null)
      setShowRoster(false)
      setShowYahooSetup(false)
      setShowComparison(false)
      setShowFlagsBrowser(false)
      setSelectedPlayer(null)
      setEnhancedData(null)
      setError(null)
    }
  }, [])

  const handleRequireYahooAuth = useCallback(() => {
    setShowAuthGate(true)
    setAuthIntent('yahoo_setup')
    setShowYahooSetup(false)
    setShowRoster(false)
  }, [])

  const handlePlayerSelect = useCallback(async (player) => {
    setSelectedPlayer(player)
    setLoading(true)
    setError(null)

    try {
      const response = await apiFetch(`/api/players/${player.sleeper_id}`)
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
          <YahooConnect
            isAuthenticated={Boolean(authUser)}
            authLoading={authLoading}
            onConnect={() => {
              setShowRoster(true)
              setShowYahooSetup(false)
            }}
            onOpenSetup={() => setShowYahooSetup(true)}
            onRequireAuth={handleRequireYahooAuth}
            onUnauthorized={handleLogout}
          />

          {/* Trends & Insights Button */}
          <button
            type="button"
            className="trends-nav-button"
            onClick={() => setShowFlagsBrowser(true)}
          >
            📊 Trends
          </button>

          {/* Compare Button */}
          <button
            type="button"
            className="compare-nav-button"
            onClick={() => setShowComparison(true)}
          >
            🔄 Compare
          </button>
        </div>

        {authUser && (
          <div className="session-row">
            <span className="session-user">{authUser.email}</span>
            <button
              type="button"
              className="session-logout"
              onClick={handleLogout}
            >
              Log Out
            </button>
          </div>
        )}
      </header>

      <main className="app-main">
        {showAuthGate && !authUser ? (
          <section className="auth-gate-section">
            <AuthPage
              onAuthenticated={handleAuthenticated}
              onCancel={() => {
                setShowAuthGate(false)
                setAuthIntent(null)
              }}
            />
            {authError && (
              <p className="auth-session-error">{authError}</p>
            )}
          </section>
        ) : showYahooSetup ? (
          authUser ? (
          <section className="yahoo-setup-section">
            <YahooSetupPage onBack={() => setShowYahooSetup(false)} />
          </section>
          ) : (
            <section className="auth-gate-section">
              <AuthPage
                onAuthenticated={handleAuthenticated}
                onCancel={() => {
                  setShowYahooSetup(false)
                  setAuthIntent(null)
                }}
              />
            </section>
          )
        ) : (
          <>
            {showRoster && authUser && (
              <section className="roster-section">
                <div className="section-header">
                  <h2>My Yahoo Roster</h2>
                  <button 
                    type="button" 
                    className="close-button"
                    onClick={() => setShowRoster(false)}
                  >
                    × Close
                  </button>
                </div>
                <RosterView />
              </section>
            )}

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
          </>
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
