import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'
import './YahooConnect.css'

function YahooConnect({ isAuthenticated, authLoading, onConnect, onOpenSetup, onRequireAuth, onUnauthorized }) {
  const [status, setStatus] = useState('disconnected') // disconnected, connecting, connected
  const [loading, setLoading] = useState(false)
  const [teamCount, setTeamCount] = useState(0)
  const [oauthConfigured, setOauthConfigured] = useState(true)

  const checkStatus = useCallback(async () => {
    if (!isAuthenticated || authLoading) {
      setStatus('disconnected')
      setTeamCount(0)
      setOauthConfigured(true)
      return
    }

    try {
      setLoading(true)
      const response = await apiFetch('/api/auth/yahoo/status')
      if (response.status === 401) {
        setStatus('disconnected')
        setTeamCount(0)
        if (onUnauthorized) {
          onUnauthorized()
        }
        return
      }
      if (response.ok) {
        const data = await response.json()
        setOauthConfigured(data.configured !== false)

        if (data.connected) {
          setStatus('connected')
          setTeamCount(data.teamCount || 0)
          if (onConnect) onConnect()
        } else {
          setStatus('disconnected')
          setTeamCount(0)
        }
      }
    } catch (err) {
      console.error('Failed to check Yahoo status:', err)
      setStatus('disconnected')
      setTeamCount(0)
      setOauthConfigured(true)
    } finally {
      setLoading(false)
    }
  }, [authLoading, isAuthenticated, onConnect, onUnauthorized])

  useEffect(() => {
    if (!isAuthenticated || authLoading) return

    checkStatus()

    const params = new URLSearchParams(window.location.search)
    if (params.get('yahoo_connected') === 'true') {
      window.history.replaceState({}, document.title, window.location.pathname)
      checkStatus()
    }
  }, [authLoading, checkStatus, isAuthenticated])

  const handleOpenSetup = () => {
    if (authLoading) return
    if (!isAuthenticated) {
      if (onRequireAuth) onRequireAuth()
      return
    }

    if (!onOpenSetup) return
    onOpenSetup()
  }

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your Yahoo Fantasy account?')) return

    try {
      setLoading(true)
      const response = await apiFetch('/api/auth/yahoo/disconnect', {
        method: 'POST'
      })
      if (response.status === 401) {
        if (onUnauthorized) {
          onUnauthorized()
        }
        return
      }
      
      if (response.ok) {
        setStatus('disconnected')
        setTeamCount(0)
        window.location.reload()
      }
    } catch (err) {
      console.error('Failed to disconnect:', err)
    } finally {
      setLoading(false)
    }
  }

  if (status === 'connected') {
    return (
      <div className="yahoo-connect connected">
        <span className="status-indicator">●</span>
        <span className="status-text">
          Yahoo Connected
          {teamCount > 0 ? ` (${teamCount} teams)` : ''}
        </span>
        <button 
          type="button"
          className="disconnect-button" 
          onClick={handleDisconnect}
          disabled={loading}
          title="Disconnect Yahoo Account"
        >
          ×
        </button>
      </div>
    )
  }

  return (
    <button 
      type="button"
      className={oauthConfigured ? 'yahoo-connect-button' : 'yahoo-setup-nav-button'}
      onClick={handleOpenSetup}
      disabled={authLoading}
    >
      <span className="yahoo-icon">Y!</span>
      {authLoading
        ? 'Checking Session...'
        : isAuthenticated
          ? (oauthConfigured ? 'Connect Yahoo Fantasy' : 'Yahoo Setup')
          : 'Sign In For Yahoo'}
    </button>
  )
}

export default YahooConnect
