import { useState, useEffect, useCallback } from 'react'
import { API_BASE_URL, apiFetch } from '../api/client'
import './YahooSetupPage.css'

const DEFAULT_REDIRECT_URI = 'https://your-domain.example/api/auth/yahoo/callback'
const REDIRECT_URI_EXAMPLE = DEFAULT_REDIRECT_URI
const OAUTH_FIELD_LABELS = {
  YAHOO_CLIENT_ID: 'Yahoo Client ID',
  YAHOO_CLIENT_SECRET: 'Yahoo Client Secret',
  YAHOO_REDIRECT_URI: 'Redirect URI',
  YAHOO_REDIRECT_URI_HTTPS: 'Redirect URI (must use HTTPS)',
}

function YahooSetupPage({ onBack }) {
  const [oauthConfigured, setOauthConfigured] = useState(false)
  const [missingEnv, setMissingEnv] = useState([])
  const [clientIdHint, setClientIdHint] = useState(null)

  const [setupForm, setSetupForm] = useState({
    clientId: '',
    clientSecret: '',
    redirectUri: DEFAULT_REDIRECT_URI,
    scope: 'fspt-r',
  })
  const [setupSaving, setSetupSaving] = useState(false)
  const [setupError, setSetupError] = useState(null)
  const [setupMessage, setSetupMessage] = useState(null)

  const loadSetupStatus = useCallback(async () => {
    try {
      const response = await apiFetch('/api/auth/yahoo/config')
      if (!response.ok) return

      const data = await response.json()
      setOauthConfigured(data.configured === true)
      setMissingEnv(data.missingEnv || [])
      setClientIdHint(data.clientIdHint || null)

      const loadedRedirectUri = (data.redirectUri || '').trim()
      const resolvedRedirectUri = loadedRedirectUri.startsWith('https://')
        ? loadedRedirectUri
        : DEFAULT_REDIRECT_URI

      setSetupForm(prev => ({
        ...prev,
        redirectUri: resolvedRedirectUri,
        scope: data.scope || 'fspt-r',
      }))
    } catch (err) {
      console.error('Failed to load Yahoo setup status:', err)
      setSetupError('Failed to load Yahoo setup status')
    }
  }, [])

  useEffect(() => {
    loadSetupStatus()
  }, [loadSetupStatus])

  const handleSetupInput = (field, value) => {
    setSetupForm(prev => ({
      ...prev,
      [field]: value,
    }))
  }

  const handleSaveSetup = async () => {
    setSetupSaving(true)
    setSetupError(null)
    setSetupMessage(null)

    let parsedRedirect = null
    try {
      parsedRedirect = new URL(setupForm.redirectUri.trim())
      if (parsedRedirect.protocol !== 'https:') {
        throw new Error('Redirect URI must start with https:// for Yahoo OAuth.')
      }
    } catch (err) {
      setSetupSaving(false)
      setSetupError(err.message || 'Redirect URI must be a valid HTTPS URL.')
      return
    }

    try {
      const response = await apiFetch('/api/auth/yahoo/config', {
        method: 'PUT',
        body: JSON.stringify({
          client_id: setupForm.clientId,
          client_secret: setupForm.clientSecret,
          redirect_uri: parsedRedirect.toString(),
          scope: setupForm.scope,
        }),
      })

      if (!response.ok) {
        let detail = 'Failed to save Yahoo OAuth settings'
        try {
          const payload = await response.json()
          detail = payload.detail || detail
        } catch {
          // Keep default detail
        }
        throw new Error(detail)
      }

      setSetupMessage('Saved. Yahoo import is ready.')
      setSetupForm(prev => ({
        ...prev,
        clientSecret: '',
      }))

      await loadSetupStatus()
    } catch (err) {
      console.error('Failed to save Yahoo setup:', err)
      setSetupError(err.message)
    } finally {
      setSetupSaving(false)
    }
  }

  const handleConnectNow = () => {
    if (!oauthConfigured) return
    const currentUrl = `${window.location.origin}${window.location.pathname}`
    const params = new URLSearchParams({
      redirect_url: currentUrl,
    })
    window.location.href = `${API_BASE_URL}/api/auth/yahoo/login?${params.toString()}`
  }

  const missingFieldLabels = missingEnv.map(field => OAUTH_FIELD_LABELS[field] || field)

  return (
    <section className="yahoo-setup-page">
      <header className="yahoo-setup-header">
        <h2>Yahoo Import Setup</h2>
        <button
          type="button"
          className="yahoo-setup-back"
          onClick={onBack}
        >
          Back to Dashboard
        </button>
      </header>

      <p className="yahoo-setup-intro">
        Configure Yahoo once here. You do not need to edit backend `.env` if you use this setup page.
      </p>

      <div className="yahoo-setup-notice">
        <h3>Before You Start</h3>
        <ul>
          <li>You need a Yahoo account with access to your Fantasy teams.</li>
          <li>You need a Yahoo Developer app at <a href="https://developer.yahoo.com/apps/" target="_blank" rel="noreferrer">developer.yahoo.com/apps</a>.</li>
          <li>This app expects Fantasy read scope <code>fspt-r</code>.</li>
          <li>Yahoo callback must be HTTPS. <strong>http://localhost callbacks will fail.</strong></li>
        </ul>
      </div>

      <div className="yahoo-setup-block">
        <h3>Step 1: Configure Yahoo Developer App (Exact Values)</h3>
        <ol className="yahoo-setup-steps">
          <li>Open <a href="https://developer.yahoo.com/apps/" target="_blank" rel="noreferrer">Yahoo Developer Apps</a> and sign in.</li>
          <li>Create a new app or open an existing app you want this dashboard to use.</li>
          <li>Create an HTTPS callback URL that reaches this backend (for local dev, use an HTTPS tunnel like ngrok/cloudflared).</li>
          <li>Find the app OAuth redirect/callback setting and paste this exact URL: <code>{setupForm.redirectUri || REDIRECT_URI_EXAMPLE}</code></li>
          <li>Set app permissions/scope to include Fantasy Sports read access: <code>fspt-r</code>.</li>
          <li>Copy both values from Yahoo app details:
            <br />
            <strong>Client ID</strong> (sometimes labeled <strong>Consumer Key</strong>)
            <br />
            <strong>Client Secret</strong> (sometimes labeled <strong>Consumer Secret</strong>)
          </li>
        </ol>
      </div>

      <div className="yahoo-setup-block">
        <h3>Step 2: Save In dbAI Pulse</h3>
        <ol className="yahoo-setup-steps">
          <li>Paste Yahoo Client ID and Client Secret below.</li>
          <li>Paste the same HTTPS Redirect URI you set in Yahoo app settings.</li>
          <li>Leave Scope as <code>fspt-r</code> for read-only team import.</li>
          <li>Click <strong>Save Yahoo Settings</strong>.</li>
          <li>After save succeeds, click <strong>Connect Yahoo Now</strong> and approve access in Yahoo.</li>
          <li>When Yahoo redirects back, return to Dashboard and open your roster.</li>
        </ol>
      </div>

      <div className="yahoo-setup-grid">
        <div className="yahoo-field">
          <label htmlFor="yahoo-client-id">Yahoo Client ID (Consumer Key)</label>
          <input
            id="yahoo-client-id"
            type="text"
            value={setupForm.clientId}
            onChange={(e) => handleSetupInput('clientId', e.target.value)}
            placeholder="ex: dj0yJmk9..."
            autoComplete="off"
          />
          <p className="yahoo-field-help">Copy from your Yahoo app details page.</p>
        </div>

        <div className="yahoo-field">
          <label htmlFor="yahoo-client-secret">Yahoo Client Secret (Consumer Secret)</label>
          <input
            id="yahoo-client-secret"
            type="password"
            value={setupForm.clientSecret}
            onChange={(e) => handleSetupInput('clientSecret', e.target.value)}
            placeholder="Paste secret exactly"
            autoComplete="off"
          />
          <p className="yahoo-field-help">Stored encrypted on this app instance.</p>
        </div>

        <div className="yahoo-field">
          <label htmlFor="yahoo-redirect-uri">Redirect URI</label>
          <input
            id="yahoo-redirect-uri"
            type="text"
            value={setupForm.redirectUri}
            onChange={(e) => handleSetupInput('redirectUri', e.target.value)}
            placeholder={REDIRECT_URI_EXAMPLE}
            autoComplete="off"
          />
          <p className="yahoo-field-help">Paste the exact callback URI from your Yahoo app settings.</p>
        </div>

        <div className="yahoo-field">
          <label htmlFor="yahoo-scope">Scope</label>
          <input
            id="yahoo-scope"
            type="text"
            value={setupForm.scope}
            onChange={(e) => handleSetupInput('scope', e.target.value)}
            autoComplete="off"
          />
          <p className="yahoo-field-help">Default read-only fantasy scope: fspt-r.</p>
        </div>
      </div>

      <div className="yahoo-setup-block yahoo-setup-troubleshooting">
        <h3>Common Errors And Exact Fix</h3>
        <ul className="yahoo-setup-errors">
          <li>Yahoo says "something went wrong" before consent screen: most often wrong Client ID (Consumer Key) or callback mismatch.</li>
          <li>No callback request hits your backend logs: callback URL is likely not HTTPS or not reachable from Yahoo.</li>
          <li><code>invalid_redirect_uri</code>: The redirect URI in Yahoo app settings does not exactly match the Redirect URI field here.</li>
          <li><code>invalid_scope</code>: Yahoo app permissions are missing Fantasy read scope <code>fspt-r</code>.</li>
          <li><code>invalid_grant</code> or expired code: Start again with <strong>Connect Yahoo Now</strong> and complete Yahoo approval immediately.</li>
          <li>Wrong key names copied: make sure Consumer Key = Client ID and Consumer Secret = Client Secret.</li>
        </ul>
      </div>

      <div className="yahoo-setup-actions">
        <button
          type="button"
          className="yahoo-save-button"
          onClick={handleSaveSetup}
          disabled={setupSaving || !setupForm.clientId || !setupForm.clientSecret || !setupForm.redirectUri}
        >
          {setupSaving ? 'Saving...' : 'Save Yahoo Settings'}
        </button>

        <button
          type="button"
          className="yahoo-connect-now"
          onClick={handleConnectNow}
          disabled={!oauthConfigured}
        >
          Connect Yahoo Now
        </button>
      </div>

      {clientIdHint && (
        <p className="yahoo-client-hint">Current app ID: {clientIdHint}</p>
      )}

      {oauthConfigured && (
        <p className="yahoo-setup-ready">
          Setup looks valid. Next: click Connect Yahoo Now, approve access, then return to dashboard.
        </p>
      )}

      {missingEnv.length > 0 && (
        <p className="yahoo-setup-missing">Still missing: {missingFieldLabels.join(', ')}</p>
      )}

      {setupError && (
        <p className="yahoo-setup-error">{setupError}</p>
      )}

      {setupMessage && (
        <p className="yahoo-setup-success">{setupMessage}</p>
      )}
    </section>
  )
}

export default YahooSetupPage
