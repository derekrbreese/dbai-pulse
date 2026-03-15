import { useState, useEffect, useCallback } from 'react'
import useHashRouter from './hooks/useHashRouter'
import { apiFetch } from './api/client'
import Layout from './components/Layout'
import DashboardHome from './components/DashboardHome'
import PlayerSearch from './components/PlayerSearch'
import PlayerDetailPage from './components/PlayerDetailPage'
import ComparisonView from './components/ComparisonView'
import FlagsBrowser from './components/FlagsBrowser'
import AuthPage from './components/AuthPage'
import YahooConnect from './components/YahooConnect'
import RosterView from './components/RosterView'
import WaiverWire from './components/WaiverWire'
import YahooSetupPage from './components/YahooSetupPage'
import ErrorBoundary from './components/ErrorBoundary'
import './App.css'

function App() {
  const { route, params, navigate } = useHashRouter()

  // Auth state
  const [authUser, setAuthUser] = useState(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [authError, setAuthError] = useState(null)
  const [showAuthGate, setShowAuthGate] = useState(false)
  const [authIntent, setAuthIntent] = useState(null)

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
      navigate('')
    }
  }, [navigate])

  const handleRequireYahooAuth = useCallback(() => {
    setShowAuthGate(true)
    setAuthIntent('yahoo_setup')
    setShowYahooSetup(false)
  }, [])

  const handlePlayerSelect = useCallback((player) => {
    navigate(`player/${player.sleeper_id}`)
  }, [navigate])

  const handleYahooConnected = useCallback(() => {
    navigate('roster')
  }, [navigate])

  const handleOpenYahooSetup = useCallback(() => {
    setShowYahooSetup(true)
  }, [])

  // Yahoo Connect component for sidebar
  const yahooConnect = (
    <YahooConnect
      isAuthenticated={Boolean(authUser)}
      authLoading={authLoading}
      onConnect={handleYahooConnected}
      onOpenSetup={handleOpenYahooSetup}
      onRequireAuth={handleRequireYahooAuth}
      onUnauthorized={handleLogout}
    />
  )

  // Auth gate helper for protected routes
  const requireAuth = (children) => {
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
    return children
  }

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
        return <DashboardHome navigate={navigate} onPlayerSelect={handlePlayerSelect} />

      case 'search':
        return (
          <div className="search-page">
            <section className="search-section">
              <PlayerSearch onPlayerSelect={handlePlayerSelect} />
            </section>
            <div className="empty-state">
              <div className="empty-icon">🔍</div>
              <h2>Search for a player</h2>
              <p>Get enhanced projections, performance flags, and AI-powered insights</p>
            </div>
          </div>
        )

      case 'player':
        return <PlayerDetailPage key={params.id} playerId={params.id} />

      case 'trends':
        return <FlagsBrowser onPlayerSelect={handlePlayerSelect} navigate={navigate} />

      case 'compare':
        return <ComparisonView params={params} />

      case 'roster':
        return requireAuth(
          <section className="roster-section">
            <RosterView onPlayerSelect={handlePlayerSelect} navigate={navigate} />
          </section>
        )

      case 'waiver':
        return requireAuth(
          <section className="waiver-section">
            <WaiverWire onPlayerSelect={handlePlayerSelect} />
          </section>
        )

      default:
        return <DashboardHome navigate={navigate} onPlayerSelect={handlePlayerSelect} />
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
      <ErrorBoundary key={route}>
        <div className="page-transition">
          {renderPage()}
        </div>
      </ErrorBoundary>
    </Layout>
  )
}

export default App
