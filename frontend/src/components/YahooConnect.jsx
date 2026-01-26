import { useState, useEffect, useCallback } from 'react'
import './YahooConnect.css'

function YahooConnect({ onConnect }) {
  const [status, setStatus] = useState('disconnected') // disconnected, connecting, connected
  const [loading, setLoading] = useState(false)

  const checkStatus = useCallback(async () => {
    try {
      setLoading(true)
      const response = await fetch('http://localhost:8000/api/auth/yahoo/status')
      if (response.ok) {
        const data = await response.json()
        if (data.connected) {
          setStatus('connected')
          if (onConnect) onConnect()
        } else {
          setStatus('disconnected')
        }
      }
    } catch (err) {
      console.error('Failed to check Yahoo status:', err)
      setStatus('disconnected')
    } finally {
      setLoading(false)
    }
  }, [onConnect])

  // Check connection status on mount and when URL params change
  useEffect(() => {
    checkStatus()
    
    // Check for success param in URL (from OAuth redirect)
    const params = new URLSearchParams(window.location.search)
    if (params.get('yahoo_connected') === 'true') {
      // Clean URL
      window.history.replaceState({}, document.title, window.location.pathname)
      checkStatus()
    }
  }, [checkStatus])

  const handleConnect = async () => {
    try {
      setLoading(true)
      // Get current URL for redirect
      const currentUrl = window.location.href
      
      // Get auth URL from backend
      await fetch(`http://localhost:8000/api/auth/yahoo/login?redirect_url=${encodeURIComponent(currentUrl)}`)
      
      // The backend returns a redirect, but fetch follows it automatically.
      // We actually want the URL to redirect the browser to.
      // Since our backend endpoint redirects, fetch might just follow it and fail CORS or return the Yahoo page HTML.
      // Better approach: backend returns the URL in JSON, or we assume the redirect URL.
      // Let's check how I implemented the backend... 
      // Ah, backend returns RedirectResponse. Fetch follows redirects by default.
      // If we use window.location.href, the backend will redirect the browser.
      
      window.location.href = `http://localhost:8000/api/auth/yahoo/login?redirect_url=${encodeURIComponent(currentUrl)}`
      
    } catch (err) {
      console.error('Failed to initiate connection:', err)
      setLoading(false)
    }
  }

  const handleDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect your Yahoo Fantasy account?')) return

    try {
      setLoading(true)
      const response = await fetch('http://localhost:8000/api/auth/yahoo/disconnect', {
        method: 'POST'
      })
      
      if (response.ok) {
        setStatus('disconnected')
        // Refresh page to clear roster data
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
        <span className="status-text">Yahoo Connected</span>
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
      className="yahoo-connect-button" 
      onClick={handleConnect}
      disabled={loading}
    >
      {loading ? (
        <span className="spinner-small"></span>
      ) : (
        <span className="yahoo-icon">Y!</span>
      )}
      Connect Yahoo Fantasy
    </button>
  )
}

export default YahooConnect
