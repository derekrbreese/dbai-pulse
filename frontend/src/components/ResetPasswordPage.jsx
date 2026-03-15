import { useState } from 'react'
import { apiFetch } from '../api/client'
import './AuthPage.css'

function ResetPasswordPage({ token, navigate }) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError('Passwords must match')
      return
    }

    setLoading(true)
    try {
      const response = await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        body: JSON.stringify({ token, password }),
      })

      if (!response.ok) {
        let detail = 'Unable to reset password'
        try {
          const payload = await response.json()
          detail = payload.detail || detail
        } catch { /* use fallback detail */ }
        throw new Error(detail)
      }

      setSuccess(true)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <section className="auth-page">
        <header className="auth-page-header">
          <h2>Invalid Link</h2>
          <p>This reset link is missing or malformed.</p>
        </header>
        <button
          type="button"
          className="auth-submit"
          onClick={() => navigate('')}
        >
          Go Home
        </button>
      </section>
    )
  }

  if (success) {
    return (
      <section className="auth-page">
        <header className="auth-page-header">
          <h2>Password Reset</h2>
          <p>Your password has been updated. You can now sign in with your new password.</p>
        </header>
        <button
          type="button"
          className="auth-submit"
          onClick={() => navigate('roster')}
        >
          Sign In
        </button>
      </section>
    )
  }

  return (
    <section className="auth-page">
      <header className="auth-page-header">
        <h2>Set New Password</h2>
        <p>Enter your new password below.</p>
      </header>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="reset-password">New Password</label>
        <input
          id="reset-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          autoComplete="new-password"
          minLength={8}
          required
        />

        <label htmlFor="reset-confirm-password">Confirm New Password</label>
        <input
          id="reset-confirm-password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Repeat password"
          autoComplete="new-password"
          minLength={8}
          required
        />

        {error && <p className="auth-error">{error}</p>}

        <button
          type="submit"
          className="auth-submit"
          disabled={loading}
        >
          {loading ? 'Resetting...' : 'Reset Password'}
        </button>
      </form>
    </section>
  )
}

export default ResetPasswordPage
