import { useState, useEffect, useCallback } from 'react'
import useHashRouter from './hooks/useHashRouter'
import { apiFetch } from './api/client'
import Layout from './components/Layout'
import DashboardHome from './components/DashboardHome'
import PlayerSearch from './components/PlayerSearch'
import EnhancedCard from './components/EnhancedCard'
import PerformanceChart from './components/PerformanceChart'
import ComparisonView from './components/ComparisonView'
import FlagsBrowser from './components/FlagsBrowser'
import AuthPage from './components/AuthPage'
import YahooConnect from './components/YahooConnect'
import RosterView from './components/RosterView'
import YahooSetupPage from './components/YahooSetupPage'
import { PlayerCardSkeleton, ChartSkeleton } from './components/SkeletonLoader'
import './App.css'

function App() {
  const { route, navigate } = useHashRouter()

  // Auth state
  const [authUser, setAuthUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState(null)
  const [showAuthGate, setShowAuthGate] = useState(false)
  const [authIntent, setAuthIntent] = useState(null)

  // Player state
  const [selectedPlayer, setSelectedPlayer] = useState(null)
  const [enhancedData, setEnhancedData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Yahoo setup
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
      setShowYahooSetup(false)
      setSelectedPlayer(null)
      setEnhancedData(null)
      setError(null)
      navigate('')
    }
  }, [navigate])

  const handleRequireYahooAuth = useCallback(() => {
    setShowAuthGate(true)
    setAuthIntent('yahoo_setup')
    setShowYahooSetup(false)
  }, [])

  const handlePlayerSelect = useCallback(async (player) => {
    setSelectedPlayer(player)
    setLoading(true)
    setError(null)

    // Navigate to search view if not already there
    if (route !== 'search' && route !== 'home') {
      navigate('search')
    }

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
  }, [navigate, route])

  // Yahoo Connect component for sidebar
  const yahooConnect = (
    <YahooConnect
      isAuthenticated={Boolean(authUser)}
      authLoading={authLoading}
      onConnect={() => navigate('roster')}
      onOpenSetup={() => setShowYahooSetup(true)}
      onRequireAuth={handleRequireYahooAuth}
      onUnauthorized={handleLogout}
    />
  )

  // Render the current page
  const renderPage = () => {
    // Auth gate takes priority
    if (showAuthGate && !authUser) {
      return (
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
      )
    }

    // Yahoo setup takes priority
    if (showYahooSetup) {
      if (!authUser) {
        return (
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
      }
      return (
        <section className="yahoo-setup-section">
          <YahooSetupPage onBack={() => setShowYahooSetup(false)} />
        </section>
      )
    }

    switch (route) {
      case 'home':
        return (
          <DashboardHome
            navigate={navigate}
            onPlayerSelect={handlePlayerSelect}
          />
        )

      case 'search':
        return (
          <div className="search-page">
            <section className="search-section">
              <PlayerSearch onPlayerSelect={handlePlayerSelect} />
            </section>

            {loading && (
              <div className="player-section">
                <PlayerCardSkeleton />
                <ChartSkeleton />
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
                <div className="empty-icon">🔍</div>
                <h2>Search for a player</h2>
                <p>Get enhanced projections, performance flags, and AI-powered insights</p>
              </div>
            )}
          </div>
        )

      case 'trends':
        return (
          <FlagsBrowser
            onPlayerSelect={handlePlayerSelect}
            navigate={navigate}
          />
        )

      case 'compare':
        return <ComparisonView />

      case 'roster':
        if (!authUser) {
          return (
            <section className="auth-gate-section">
              <AuthPage
                onAuthenticated={handleAuthenticated}
                onCancel={() => navigate('')}
              />
            </section>
          )
        }
        return (
          <section className="roster-section">
            <RosterView />
          </section>
        )

      default:
        return (
          <DashboardHome
            navigate={navigate}
            onPlayerSelect={handlePlayerSelect}
          />
        )
    }
  }

  return (
    <Layout
      route={route}
      navigate={navigate}
      authUser={authUser}
      onLogout={handleLogout}
      yahooConnect={yahooConnect}
    >
      <div key={route} className="page-transition">
        {renderPage()}
      </div>
    </Layout>
  )
}

export default App
