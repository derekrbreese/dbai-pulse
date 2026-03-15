import { useState } from 'react'
import { apiFetch } from '../api/client'
import './AuthPage.css'

function ChangePasswordPage() {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setSuccess(false)

    if (newPassword !== confirmPassword) {
      setError('New passwords must match')
      return
    }

    if (currentPassword === newPassword) {
      setError('New password must be different from current password')
      return
    }

    setLoading(true)
    try {
      const response = await apiFetch('/api/auth/change-password', {
        method: 'PUT',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })

      if (!response.ok) {
        let detail = 'Unable to change password'
        try {
          const payload = await response.json()
          detail = payload.detail || detail
        } catch { /* use fallback detail */ }
        throw new Error(detail)
      }

      setSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="auth-page">
      <header className="auth-page-header">
        <h2>Change Password</h2>
        <p>Update your account password.</p>
      </header>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label htmlFor="current-password">Current Password</label>
        <input
          id="current-password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          autoComplete="current-password"
          required
        />

        <label htmlFor="new-password">New Password</label>
        <input
          id="new-password"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          placeholder="At least 8 characters"
          autoComplete="new-password"
          minLength={8}
          required
        />

        <label htmlFor="confirm-new-password">Confirm New Password</label>
        <input
          id="confirm-new-password"
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          placeholder="Repeat new password"
          autoComplete="new-password"
          minLength={8}
          required
        />

        {error && <p className="auth-error">{error}</p>}
        {success && <p className="auth-success">Password updated successfully.</p>}

        <button
          type="submit"
          className="auth-submit"
          disabled={loading}
        >
          {loading ? 'Updating...' : 'Update Password'}
        </button>
      </form>
    </section>
  )
}

export default ChangePasswordPage
