import { useState } from 'react'
import { apiFetch } from '../api/client'
import './AuthPage.css'

function AuthPage({ onAuthenticated, onCancel = null }) {
    const [mode, setMode] = useState('login')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const handleSubmit = async (e) => {
        e.preventDefault()
        setError(null)

        if (mode === 'register' && password !== confirmPassword) {
            setError('Passwords must match')
            return
        }

        setLoading(true)
        try {
            const endpoint = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
            const response = await apiFetch(endpoint, {
                method: 'POST',
                body: JSON.stringify({
                    email: email.trim(),
                    password,
                }),
            })

            if (!response.ok) {
                let detail = mode === 'login'
                    ? 'Unable to sign in'
                    : 'Unable to create account'
                try {
                    const payload = await response.json()
                    detail = payload.detail || detail
                } catch {
                    // Preserve fallback detail.
                }
                throw new Error(detail)
            }

            const session = await response.json()
            if (session.authenticated && session.user) {
                onAuthenticated(session.user)
                return
            }

            throw new Error('Authentication did not complete')
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <section className="auth-page">
            <header className="auth-page-header">
                <h2>{mode === 'login' ? 'Sign In' : 'Create Account'}</h2>
                <p>Log in to connect Yahoo and save your team feedback preferences.</p>
            </header>

            <div className="auth-toggle">
                <button
                    type="button"
                    className={mode === 'login' ? 'active' : ''}
                    onClick={() => {
                        setMode('login')
                        setError(null)
                    }}
                >
                    Sign In
                </button>
                <button
                    type="button"
                    className={mode === 'register' ? 'active' : ''}
                    onClick={() => {
                        setMode('register')
                        setError(null)
                    }}
                >
                    Create Account
                </button>
            </div>

            <form className="auth-form" onSubmit={handleSubmit}>
                <label htmlFor="auth-email">Email</label>
                <input
                    id="auth-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    autoComplete="email"
                    required
                />

                <label htmlFor="auth-password">Password</label>
                <input
                    id="auth-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="At least 8 characters"
                    autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                    minLength={8}
                    required
                />

                {mode === 'register' && (
                    <>
                        <label htmlFor="auth-confirm-password">Confirm Password</label>
                        <input
                            id="auth-confirm-password"
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            placeholder="Repeat password"
                            autoComplete="new-password"
                            minLength={8}
                            required
                        />
                    </>
                )}

                {error && (
                    <p className="auth-error">{error}</p>
                )}

                <button
                    type="submit"
                    className="auth-submit"
                    disabled={loading}
                >
                    {loading
                        ? (mode === 'login' ? 'Signing In...' : 'Creating Account...')
                        : (mode === 'login' ? 'Sign In' : 'Create Account')}
                </button>
            </form>

            {onCancel && (
                <button
                    type="button"
                    className="auth-cancel"
                    onClick={onCancel}
                >
                    Continue Without Yahoo
                </button>
            )}
        </section>
    )
}

export default AuthPage
